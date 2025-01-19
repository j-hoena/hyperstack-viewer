# -*- coding: utf-8 -*-
"""
Created on Tue Aug 20 17:21:52 2024

@author: Johannes Hoena
"""


import tkinter as tk
from tkinter import Label
from tkinter import Button
from tkinter import LabelFrame
from tkinter import Canvas
from tkinter import DoubleVar
from tkinter import Menu
from tkinter import Checkbutton
from tkinter import Toplevel
from tkinter import Tk

from tkinter import filedialog, messagebox, simpledialog
from tkinter.filedialog import asksaveasfile 
from tkinter import ttk

from PIL import Image, ImageTk, ImageEnhance, ImageDraw
from PIL.TiffTags import TAGS

import re

import numpy as np

import matplotlib.pyplot as plt

import torch

import cv2

from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from matplotlib.figure import Figure
    
import traceback    

import skimage

#import keyboard
import sys

import roifile

import os

class CustomNavigationToolbar(NavigationToolbar2Tk):
    '''Override zum Deaktivieren der Koordinaten-Ausgabe im 3d-Plot'''
    

    def set_message(self, message):
        # Überschreiben der Methode zum Entfernen der Koordinaten-Anzeige
        pass


class HyperstackViewer:
    '''Klasse des Hauptfensters, welches alle GUI-Elemente, Bild-Arrays und das YOLO-Modell enthält.

       Parameter
       -----------
       root : Tk
           Tk-Objekt des tkinter-module 

    '''
    
    
    def __init__(self, root):    
        
            
        '''Anzahl der Cluster, in die YOLO-Detections zerlegt werden'''
        self.num_clusters = 7
        
        '''Aktuelle Cursor-Koordinaten'''
        self.cursor_x = 0
        self.cursor_y = 0
        
        
        '''Confidence-Threshold zum Anzeigen der Cluster-Detections'''
        self.yolo_threshold = 0.5
        
        self.draw_clusters = False
        self.draw_plastides = False

        
        '''Variablen zum Speichern des Modells und der Detections'''
        self.model = 0
        
        '''unused'''
        self.detections = 0
        
        '''Array zum Speichern der Plastiden-Koordinaten'''
        self.plastid_coords = []
        
        self.plastide_edit_mode = False
        
        '''Breite und Hoehe des Fensters'''
        self.canvas_width  = 900
        self.canvas_height = 900
        
        
        '''Parameter zur Manipulation des Bildes'''
        self.contrast_value = 1 
        self.brightness_value = 1
        self.zoom = 1.0
        self.offset_x = 0
        self.offset_y = 0
        
        '''Bild-Arrays'''
        self.pilimages = []
        self.origimages = []
        self.current_img = 0
        
        self.img_path = ""
        
        
        '''Indexes zur Navigation durch die Stacks'''
        self.n_frames = 0
        self.z_layers = 0
        self.timestamps = 0
        self.hist_bins = 0
        
        ''' z- und t-index zur Navigation durch den Stack '''
        self.z_index  =  0
        self.t_index = 0
        
        self.root = root
        self.root.title("Hyperstack Viewer")
        #self.root.attributes("-topmost", True)
        
        
        
        '''Komposition der Menu-Elemente'''
        self.menu = Menu(root)
        self.root.config(menu=self.menu)
        
        
        self.file_menu = Menu(self.menu, tearoff=0)
        self.edit_menu = Menu(self.menu, tearoff=0)
        
        
        self.menu.add_cascade(label="File", menu=self.file_menu)
        self.menu.add_cascade(label="Edit", menu=self.edit_menu)
        
        
        self.file_menu.add_command(label="Open Stack", command=self.open_stack)
        self.file_menu.add_command(label="Export ROIs", command=self.export)
        self.file_menu.add_command(label="Load YOLO-Model", command=self.load_yolo)
        self.file_menu.add_separator()
        self.file_menu.add_command(label="Exit", command=self.on_closing)
        
        self.edit_menu.add_command(label="Brightness & Contrast", command=self.edit_bc)
        self.edit_menu.add_command(label="Histogram Slicing", command=self.hist_slice)
        self.edit_menu.add_command(label="Histogram Equalization", command=self.hist_equal)
        self.edit_menu.add_command(label="Reset Changes", command=self.edit_reset)
        
        
        
        '''Schaltflaechen erst klickbar, wenn Stack geladen wurde'''
        self.edit_menu.entryconfig("Brightness & Contrast", state = "disabled")
        self.edit_menu.entryconfig("Histogram Slicing", state = "disabled")
        self.edit_menu.entryconfig("Histogram Equalization", state = "disabled")
        self.edit_menu.entryconfig("Reset Changes", state = "disabled")
        
        
        self.file_menu.entryconfig("Export ROIs", state = "disabled")
        self.file_menu.entryconfig("Load YOLO-Model", state = "disabled")
        
        self.parentframe= LabelFrame(root,text="Hyperstack Viewer")
        
        
        self.mainframe = LabelFrame(self.parentframe,text="Image")
        self.mainframe.grid(row=0,column=0,rowspan=2)
   
        
        
        
        
        '''Konfiguration der Navigations-Schaltflaechen'''
        
        self.zbutton_back = Button(self.mainframe,text="<<", command = self.z_prev)
        self.label_z = Label(self.mainframe,text="Z Axis")
        self.zbutton_next = Button(self.mainframe, text=">>", command = self.z_next)
        
        
        self.zbutton_back.grid(row=1,column=0)
        self.label_z.grid(row=1,column=1)
        self.zbutton_next.grid(row=1,column=2)
        
        
        self.tbutton_back = Button(self.mainframe,text="<<", command = self.t_prev)
        self.label_t = Label(self.mainframe,text="Time")
        self.tbutton_next = Button(self.mainframe, text=">>", command = self.t_next)
        
        
        self.tbutton_back.grid(row=2,column=0)
        self.label_t.grid(row=2,column=1)
        self.tbutton_next.grid(row=2,column=2)
        
        self.zbutton_back.config(state = "disabled")
        self.zbutton_next.config(state = "disabled")
        self.tbutton_back.config(state = "disabled")
        self.tbutton_next.config(state = "disabled")
        
        self.xylabel = Label(self.mainframe, text = "[X, Y]")
        self.xylabel.grid(row=3,column=1)
        
        

        '''IMG-Canvas zum Darstellen des Bildes'''
        
        self.img_canvas = Canvas(self.mainframe, background="black", width=self.canvas_width,height=self.canvas_height)
        self.img_canvas.grid(row=0,column=0,columnspan=3)
        
        
        '''linksklick'''
        self.img_canvas.bind("<Button-1>", self.mouse_down_left)   
        
        '''rechtsklick'''        
        self.img_canvas.bind("<Button-3>", self.mouse_down_right) 
        
        '''drag bei linksklick + bewegung'''                
        self.img_canvas.bind("<B1-Motion>", self.mouse_move_left)
        
        '''bewegung ohne klick'''
        self.img_canvas.bind("<Motion>", self.mouse_move)
        
        '''Doppelklick'''                    
        self.img_canvas.bind("<Double-Button-1>", self.mouse_double_click_left) 
        
        '''zoom per mousewheel'''
        self.img_canvas.bind("<MouseWheel>", self.mouse_wheel) 
        
        '''Zoom Linux'''
        self.img_canvas.bind("<Button-4>", self.mouse_wheel_linux)
        self.img_canvas.bind("<Button-5>", self.mouse_wheel_linux)
        
        
        self.toolbarframe = LabelFrame(self.parentframe,text="Toolbar",width=self.canvas_width/2, height=self.canvas_height)
        self.toolbarframe.grid(row=0,column=1,rowspan=2)
        
        
        '''Optionen fuer Ansicht'''
        self.toolframe = LabelFrame(self.toolbarframe, text="View")
        self.toolframe.grid(row=0,column=0)
        
        '''Plastide Edit Mode'''
        self.edit_plastide_frame = LabelFrame(self.toolbarframe, text="ROI")
        self.edit_plastide_frame.grid(row=1,column=0)
 
        '''Anzeige Histogramm'''       
        self.histframe = LabelFrame(self.toolbarframe,text="Histogram")
        self.histframe.grid(row=2,column=0)
        
        self.histlabel = Label(self.histframe,text="")
        self.histlabel.grid(row=0,column=0)
        

        '''3D-Plot'''  
        self.plotframe = LabelFrame(self.toolbarframe, text="3D Plot")
        self.plotframe.grid(row=3,column=0)
        
        self.plotlabel = Label(self.plotframe,text="")
        self.plotlabel.grid(row=0,column=0)
        
        self.placeholder_label = Label(self.toolbarframe, text="",height = 10)
        self.placeholder_label.grid(row=4,column=0)
        
        '''Ansicht-Buttons'''
        self.brightnessbutton_down = Button(self.toolframe, text ="<<", command=self.brightness_down)
        self.label_brightness = Label(self.toolframe,text=f"Brightness: {self.brightness_value:.1f}")
        self.brightnessbutton_up = Button(self.toolframe, text =">>", command=self.brightness_up)
        
        self.brightnessbutton_down.grid(row=0,column=0)
        self.label_brightness.grid(row=0,column=1)
        self.brightnessbutton_up.grid(row=0,column=2)

        self.contrastbutton_down = Button(self.toolframe, text ="<<", command=self.contrast_down)
        self.label_contrast = Label(self.toolframe,text=f"Contrast: {self.contrast_value:.1f}")
        self.contrastbutton_up = Button(self.toolframe, text =">>", command=self.contrast_up)

        self.contrastbutton_down.grid(row=1,column=0)
        self.label_contrast.grid(row=1,column=1)
        self.contrastbutton_up.grid(row=1,column=2)
        
        self.view_reset_button= Button(self.toolframe, text = "Reset", command=self.reset_view)
        self.view_reset_button.grid(row=2,column=1)
        
        self.threshbutton_down = Button(self.toolframe, text ="<<", command=self.thresh_down)
        self.label_thresh = Label(self.toolframe,text=f"Yolo Threshold: {self.yolo_threshold:.1f}")
        self.threshbutton_up = Button(self.toolframe, text =">>", command=self.thresh_up)
        
        self.threshbutton_down.grid(row=3,column=0)
        self.label_thresh.grid(row=3,column=1)
        self.threshbutton_up.grid(row=3,column=2)
        
        self.yolo_toggle_button = Checkbutton(self.toolframe, text="Draw Detections", command=self.toggle_yolo)
        self.yolo_toggle_button.grid(row=4,column=1)
        
        self.plastid_toggle_button = Checkbutton(self.toolframe, text="Draw Plastids", command=self.toggle_plastides)
        self.plastid_toggle_button.grid(row=5,column=1)
        
        
        
        '''Plastid Edit'''
        self.plastide_edit_button = Button(self.edit_plastide_frame, text = "Edit Plastids", command=self.toggle_edit_mode)
        self.plastide_edit_button.grid(row=0,column=0)
        
        self.plastide_edit_label = Label(self.edit_plastide_frame, text = "Edit Mode: Off")
        self.plastide_edit_label.grid(row=1,column=0)
        
        self.plastide_edit_button.config(state="disabled")
        
        
        '''Deaktivieren bis Stack geladen wurde'''
        self.yolo_toggle_button.config(state = "disabled")
        self.plastid_toggle_button.config(state = "disabled")
        self.contrastbutton_down.config(state = "disabled")
        self.contrastbutton_up.config(state = "disabled")
        self.brightnessbutton_down.config(state = "disabled")
        self.brightnessbutton_up.config(state = "disabled")
        self.threshbutton_down.config(state = "disabled")
        self.threshbutton_up.config(state = "disabled")
        
        
        '''Hotkeys - sehr schlechte Performance'''
        # keyboard.add_hotkey('up', self.z_next)
        # keyboard.add_hotkey('down', self.z_prev)
        # keyboard.add_hotkey('left', self.t_prev)
        # keyboard.add_hotkey('right', self.t_next)
        # keyboard.add_hotkey('ctrl+r', self.toggle_edit_mode)
        
        self.parentframe.grid(row=0,column=0)
        
        
        self.root.grid_rowconfigure(0, weight=1)
        self.root.grid_columnconfigure(0, weight=1)
        
        '''Toolbar Items fuer die Plots'''
        NavigationToolbar2Tk.toolitems = [t for t in NavigationToolbar2Tk.toolitems if
                                  t[0] in ('Home', 'Pan', 'Zoom','Save')]
        
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        
        self.reset_transform()
        self.root.mainloop()
        
        return
    
    
    def on_closing(self):
        if messagebox.askokcancel("Quit", "Do you want to quit?"):
            self.root.destroy()
            sys.exit()
    
    def toggle_yolo(self):
        '''Methode zum umschalten der Anzeige der Bounding Boxen'''
        self.draw_detections =  not self.draw_detections
        self.update_img()
        
    def toggle_plastides(self):
        '''Methode zum umschalten der Anzeige der Plastiden'''
        self.draw_plastides =  not self.draw_plastides
        self.update_img()
        
        
    def open_stack(self):
        self.open_file(0)
    
    def deactivate_gui(self):
           
        self.menu.entryconfig(1, state="disabled")
        self.menu.entryconfig(2,state="disabled")
        
        self.file_menu.entryconfig("Load YOLO-Model", state = "disabled")
        self.file_menu.entryconfig("Export ROIs", state = "disabled")
        self.edit_menu.entryconfig("Brightness & Contrast", state = "disabled")
        self.edit_menu.entryconfig("Histogram Slicing", state = "disabled")
        self.edit_menu.entryconfig("Histogram Equalization", state = "disabled")
        self.edit_menu.entryconfig("Reset Changes", state = "disabled")
        
        '''Deaktiviere Navigation durch Stack'''
        self.zbutton_back.config(state = "disabled")
        self.zbutton_next.config(state = "disabled")
        self.tbutton_back.config(state = "disabled")
        self.tbutton_next.config(state = "disabled")
        
        
        '''Deaktiviere Bild-Modifikation'''
        self.contrastbutton_down.config(state = "disabled")
        self.contrastbutton_up.config(state = "disabled")
        self.brightnessbutton_down.config(state = "disabled")
        self.brightnessbutton_up.config(state = "disabled")
        
        self.plastide_edit_button.config(state="disabled")
        self.plastid_toggle_button.config(state = "disabled")
        
        
    def activate_gui(self):
        
        self.menu.entryconfig(1, state="normal")
        self.menu.entryconfig(2,state="normal")
        
        self.file_menu.entryconfig("Load YOLO-Model", state = "normal")
        self.file_menu.entryconfig("Export ROIs", state = "normal")
        self.edit_menu.entryconfig("Brightness & Contrast", state = "normal")
        self.edit_menu.entryconfig("Histogram Slicing", state = "normal")
        self.edit_menu.entryconfig("Histogram Equalization", state = "normal")
        self.edit_menu.entryconfig("Reset Changes", state = "normal")
        
        '''Aktiviere Navigation durch Stack'''
        self.zbutton_back.config(state = "normal")
        self.zbutton_next.config(state = "normal")
        self.tbutton_back.config(state = "normal")
        self.tbutton_next.config(state = "normal")
        
        
        '''Aktiviere Bild-Modifikation'''
        self.contrastbutton_down.config(state = "normal")
        self.contrastbutton_up.config(state = "normal")
        self.brightnessbutton_down.config(state = "normal")
        self.brightnessbutton_up.config(state = "normal")
        
        self.plastide_edit_button.config(state="normal")
        self.plastid_toggle_button.config(state = "normal")
    
    def open_file(self,mode):
        '''Methode zum laden eines Tiff-Stacks'''
        
        try:
            '''mode 0: ermitteln des filepaths
               mode 1: neu laden aus vorhandenem filepath           
            '''
            if mode == 0:
                file_path = filedialog.askopenfile(title="Choose TIFF stack", filetypes=[("Tiff images", "*.tif")],parent = self.root)
                
                if not file_path:
                    return
                
                self.image_path = file_path.name
            
            '''Disable, falls Vorgang fehlschlaegt'''
            self.deactivate_gui()
            
            
            '''Reset der internen Variablen'''
            self.pilimages = []
            self.origimages = []
            
            self.cropped_images = []
            
            self.plastid_coords = []
            
            self.current_img = 0
            
            self.model = 0
            self.detections = 0
            
            self.yolo_toggle_button.deselect()
            self.draw_detections = False
            
            
            self.n_frames = 0
            self.z_layers = 0
            self.timestamps = 0
            
            self.z_index  =  0
            self.t_index = 0
            

            self.yolo_toggle_button.config(state = "disabled")
            self.threshbutton_down.config(state = "disabled")
            self.threshbutton_up.config(state = "disabled")
            
            
            if self.image_path:
                    
                image = Image.open(self.image_path)
                
                try:
                    
                    '''Extrahiere Metadaten'''
                    meta_dict = {TAGS[key] : image.tag[key] for key in image.tag_v2}
                    info = meta_dict["ImageDescription"][0]
                    
                    
                    
                    self.z_layers = int(re.search(r'slices=(\d+)', info).group(1))
                    
                    
                    '''Sonderfall falls t=1'''
                    t_frames = re.search(r'frames=(\d+)', info)
                    if t_frames is None:
                        self.timestamps = 1 
                    else: 
                        self.timestamps = int(t_frames.group(1))
        
                    if image.mode == "I;16B":
                        '''16 bit int'''
                        self.hist_bins = 65536
                    else:
                        '''8 bit int'''
                        self.hist_bins = 256
                    
                    
                    print(image.n_frames)
                    self.n_frames = image.n_frames
                except:
                    traceback.print_exc()
                    m = "Metadaten des TiffStacks (frames, slices) konnten nicht erfasst werden. Bitte Datei überprüfen."
                    tk.messagebox.showinfo(title="Fehler", message=m)
                    return
                
                
                pil_img = []
                orig_img = []
                
                
                '''ProgressBar'''
                
                popup = Toplevel()
                popup.attributes("-topmost", True)
                Label(popup, text="Loading Slices...").grid(row=0,column=0)
                progress_var = DoubleVar()
                progress_bar = ttk.Progressbar(popup, variable=progress_var, maximum=self.n_frames)
                progress_bar.grid(row=1, column=0)#.pack(fill=tk.X, expand=1, side=tk.BOTTOM)
                popup.pack_slaves()
                
                progress = 0
                progressstep = 1
                
                print("image mode:")
                print(image.mode)
                
                
                try:
                    
                    '''Slices Laden und in interne Array-Struktur ueberfuehren'''
                    
                    page_number = 0
                    while True:
                        print(f"Seite {page_number + 1}")
                        
                        temp = image.convert("I")
    
                        '''Konvertiere in 8Bit zur Darstellung in tkinter'''
                        temp = temp.point(lambda i: i*(1/255)).convert("RGB")
                        temp = temp.convert('L')
                        
                        pil_img.append(temp)
                        
                        '''Originales Slice behalten'''
                        orig_img.append(np.asarray(image))
                        page_number += 1
                        image.seek(page_number)
                        
                        
                        
                        progress += progressstep
                        progress_var.set(progress)
                        popup.update()
                        
                        
                except EOFError:
        
                    print("Ende der Datei erreicht.")
                
                print("Länge Arrays")
                print(len(pil_img))
                print(len(orig_img))
                print("progress")
                print(progress)
                index = 0
                
                '''Aufteilung nach Frames und Slices wiederherstellen'''
                for i in range(self.timestamps):
                    temp_pil =[]
                    temp_origimg =[]
                    
                    self.plastid_coords.append([])
                    
                    for j in range(self.z_layers):
                        print(index)
                        temp_pil.append(pil_img[index])
                        temp_origimg.append(orig_img[index])
                        index += 1
                        
                        self.plastid_coords[i].append([])
                        
                        progress += progressstep
                        progress_var.set(progress)
                        popup.update()
    
                        
                        
                    self.pilimages.append(temp_pil)
                    self.origimages.append(temp_origimg)
        
                
                print(len(self.pilimages))
                print(len(self.origimages))
                
                self.activate_gui()
                
                popup.destroy()
                
                
                print("progress")
                print(progress)
                
                self.placeholder_label.destroy()
                self.placeholder_label = Label(self.toolbarframe, text="",height = 2)
                self.placeholder_label.grid(row=4,column=0)
                
                self.mainframe.config(text = file_path.name)
                
                self.update_img()
                self.draw_hist(self.origimages[self.t_index][self.z_index])
                self.draw_plot()
                
        except Exception as e:
            traceback.print_exc()
            m = "Fehler beim Oeffnen der Datei. " + str(e)
            tk.messagebox.showinfo(title="Fehler", message=m)
            self.menu.entryconfig(1, state="normal")
            
            return    
       
    
    def draw_hist(self,img):
        '''Erstellt histogramm fuer Bild und zeichnet es im Histogramm-Frame'''
        
        try:
            
            print(self.hist_bins)
            imhist,bins = np.histogram(img.flatten(), bins = self.hist_bins,range=(0, self.hist_bins-1))
        
            fig, ax = plt.subplots(figsize=(4, 3), dpi=100)
            fig.subplots_adjust(left=0.21,bottom=0.2)

            ax.plot(bins[:-1],imhist, color='black')
            ax.set_title("Histogram")
            ax.set_xlabel("Pixel value")
            ax.set_ylabel("Frequency")
       
            #if hasattr(self, 'hist_canvas'):
             #   self.hist_canvas.get_tk_widget().destroy()
        
            self.hist_canvas = FigureCanvasTkAgg(fig, master=self.histframe)
           
            self.hist_canvas.draw()
            self.hist_canvas.get_tk_widget().grid(row=0, column=0)
           
            self.histtoolbar = CustomNavigationToolbar(self.hist_canvas, self.histframe,pack_toolbar=False)
            self.histtoolbar.update()
            self.histtoolbar.grid(row=1,column=0)
            
            plt.close()
            
        except Exception as e:
            traceback.print_exc()
            print("exception: " + str(type(e)))
    
    
    
    def update_img(self):
        '''Updated das angezeigte Bild nach Indexaenderung'''
        
        
        
        '''Neues Bild aus dem PIL-Image-Array holen und Filter anwenden'''
        self.temp = self.pilimages[self.t_index][self.z_index]
        self.temp = self.apply_filters(self.temp)
        
        '''Zeige Detections, falls Modell geladen wurde bool=true'''
        if self.model != 0 and self.draw_detections:            
            self.draw_yolo()
        
        if self.draw_plastides:   
            self.draw_plastid_ellipse()
        
        '''Zoom-Einstellungen zurücksetzen'''
        self.reset_zoom(self.temp.height,self.temp.width)
        self.draw_image()
        
        
        '''Aktualisiere Index'''
        self.label_t.config(text=f"t:  {self.t_index+1}/{self.timestamps}")
        self.label_z.config(text=f"z:  {self.z_index+1}/{self.z_layers}")
        

    
    def apply_filters(self, img):
        '''Wendet Helligkeits- und Kontrastaenderung auf Pil-Image an'''
        
        if self.brightness_value != 1 or self.contrast_value != 1:
            
            '''Nutze Enhancer der PIL-Library, um Image-Objekte direkt zu modifizieren'''            
            enhancer = ImageEnhance.Brightness(img)
            img = enhancer.enhance(self.brightness_value)
            enhancer = ImageEnhance.Contrast(img)
            img = enhancer.enhance(self.contrast_value)
        
        return img



    def reset_zoom(self, image_width, image_height):
        '''Setzt den Zoom bei Aenderung des Index oder Doppelklick auf Canvas zurueck'''

        if (image_width * image_height <= 0) or (self.canvas_width * self.canvas_height <= 0):
            return


        self.reset_transform()

        scale = 1.0
        offsetx = 0.0
        offsety = 0.0

        if (self.canvas_width * image_height) > (image_width * self.canvas_height):
    
            scale = self.canvas_height / image_height

            offsetx = (self.canvas_width - image_width * scale) / 2
        else:

            scale = self.canvas_width / image_width

            offsety = (self.canvas_height - image_height * scale) / 2


        self.scale(scale)

        self.translate(offsetx, offsety)



    def draw_image(self):
        '''Transformiert Bild mit Transformationsmatrix und hinterlegt es im Canvas'''
        
        mat_inv = np.linalg.inv(self.mat_affine)
        
        affine_inv = (
            mat_inv[0, 0], mat_inv[0, 1], mat_inv[0, 2],
            mat_inv[1, 0], mat_inv[1, 1], mat_inv[1, 2]
             )
         
        dst = self.temp.transform(
                    (self.canvas_width, self.canvas_height),
                    Image.AFFINE,  
                    affine_inv,     
                    Image.NEAREST      
                    )
        
        if self.plastide_edit_mode:
            dst = dst.convert("RGBA")
            draw = ImageDraw.Draw(dst)
            draw.text([10,10],"Edit Plastids - Left Click: Add - Right Click: Remove", fill=(0,255,0),font_size=15)
            
        self.current_img = ImageTk.PhotoImage(dst)
         
        item = self.img_canvas.create_image(
                0, 0,        
                anchor='nw',   
                image=self.current_img     
                )
         
    def load_yolo(self):
        '''Methode zum Laden des YOLO-Modells und Durchfuehren der Inferenz'''
        try:
            weights_path = filedialog.askopenfile(title="Choose YOLO Weights", filetypes=[("YOLO weights","*.pt")],parent = self.root)
            if not weights_path:  # abort
                return
            if weights_path:  
                
                
                self.deactivate_gui()
            
                self.yolo_toggle_button.config(state = "disabled")
                self.threshbutton_down.config(state = "disabled")
                self.threshbutton_up.config(state = "disabled")
                
                popup = Toplevel()
                popup.attributes("-topmost", True)
                Label(popup, text="Loading Predictions...").grid(row=0,column=0)
                progress_var = DoubleVar()
                progress_bar = ttk.Progressbar(popup, variable=progress_var, maximum=self.n_frames)
                progress_bar.grid(row=1, column=0)
                popup.pack_slaves()
                
                progress = 0
                progressstep = 1        
                
                self.model = torch.hub.load('ultralytics/yolov5', "custom", path=weights_path.name, force_reload=True)
                
                self.detections = []

                for i in range(self.timestamps):
                  
        
                    temp_arr = []
                    
                    for j in range(self.z_layers):
                        
                        temp_img = self.pilimages[i][j]
                        temp_img_orig = Image.fromarray(self.origimages[i][j])

                        #Inferenz funktioniert nur auf 8bit-int
                        results = self.model(temp_img)
                        
                        results_formatted = results.pandas().xyxy[0].to_dict(orient="records")
                        print("number of results:")
                        print(len(results_formatted))
                        temp_arr.append(results_formatted)
                       
                        count = 0

                        for x in results_formatted:
                            x1, y1, x2, y2 = int(x['xmin']), int(x['ymin']), int(x['xmax']), int(x['ymax'])
                        
                            border = [x1,y1,x2,y2]
                            print(border)
                            '''Crop die Detection zur Segmentierung'''
                            temp_crop = temp_img_orig.crop(border)
                            print(np.asarray(temp_crop).shape)

                            
                            #Plastiden-Segmentierung
                            coords = self.plastid_segmentation(np.asarray(temp_crop))
                            
                            for c in coords:
                                self.plastid_coords[i][j].append((c[0]+x1,c[1]+y1))
                            
                            count += 1
         
                        progress += progressstep
                        progress_var.set(progress)
                        popup.update()
                        

                    self.detections.append(temp_arr)    
            
            
                popup.destroy()
                
                self.yolo_toggle_button.config(state = "normal")
                self.threshbutton_down.config(state = "normal")
                self.threshbutton_up.config(state = "normal")
                
                self.activate_gui()
                
                
                
                self.draw_plot()
                
                print("len detections")
                print(len(self.detections))
                self.update_img()
                return    
        except Exception as e:
            traceback.print_exc()
            m = "Fehler bei der YOLO-Inferenz. " + str(e)
            tk.messagebox.showinfo(title="Fehler", message=m)
            popup.destroy()
            self.activate_gui()
            return    

    def draw_plastid_ellipse(self):
        '''Zeichnet Plastiden des aktuellen z-Slices'''
        
        self.temp = self.temp.convert("RGBA")
        draw = ImageDraw.Draw(self.temp)
        plastide_count = 0
        coords= self.plastid_coords[self.t_index][self.z_index]
  

        for c in coords:
            
            '''Ellipse mit Zentrum erstellen'''
            x_min = int(c[0]-4)
            y_min = int(c[1]-4)
            
            x_max = int(c[0]+4)
            y_max = int(c[1]+4)
            
            draw.ellipse([x_min,y_min,x_max,y_max], outline="#00ff00")
            #draw.text([x_min,y_min],f"{plastide_count+1}")
            
            plastide_count += 1
        
        
        return


    def draw_yolo(self):
        '''zeichnet Bounding Boxenfuer aktuelles Slice'''
        print("draw")
        
        detections = self.detections[self.t_index][self.z_index]  
        
        self.temp = self.temp.convert("RGBA")
        draw = ImageDraw.Draw(self.temp)
   
      
        count = 0
        for x in detections:
            x1, y1, x2, y2 = int(x['xmin']), int(x['ymin']), int(x['xmax']), int(x['ymax'])
            confidence = x['confidence']
            
            if confidence > self.yolo_threshold:
                draw.rectangle([x1,y1,x2,y2], width = 1, outline="#0000ff")
                draw.text([x1-15,y1-5],f"c {count+1}")
                
                count += 1
            

        
    def draw_plot(self):
        '''Erstellt 3D-Plot der erkannten Plastiden und bettet ihn in plotframe ein'''
        print("t_index")
        print(self.t_index)
        
        temp = self.pilimages[self.t_index][self.z_index]
        

        x_arr = []
        y_arr = []
        z_arr = []
        
        
        '''Koordinaten der Plastiden extrahieren'''
        for i in range(self.z_layers):
            
            coords = self.plastid_coords[self.t_index][i]
            
            for c in coords:
                x_arr.append(c[0])
                y_arr.append(c[1])
                z_arr.append(i)
            
        
        fig = Figure(figsize=(4, 3), dpi=100)
        ax = fig.add_subplot(111, projection='3d')
        
        ax.scatter(x_arr, y_arr, z_arr, c='r', marker='o')
        
        ax.set_title(f"t-frame {self.t_index+1}")
        ax.set_xlabel('X')
        ax.set_ylabel('Y')
        ax.set_zlabel('Z')
        
        ax.set_xlim(0,temp.width)
        ax.set_ylim(0,temp.height)
        ax.set_zlim(0,self.z_layers)
        
        ax.invert_yaxis()  # Y-Achse invertieren
        
       
        
        if hasattr(self, 'zplotcanvas'):
            self.zplotcanvas.get_tk_widget().destroy()
            
        if hasattr(self, 'zplottoolbar'):
            self.zplottoolbar.destroy()
        
        self.zplotcanvas = FigureCanvasTkAgg(fig, master=self.plotframe)
        self.zplotcanvas.draw()

        self.zplottoolbar = CustomNavigationToolbar(self.zplotcanvas, self.plotframe,pack_toolbar=False)
        self.zplottoolbar.update()
        
        # Canvas im Tkinter-Fenster platzieren
        self.zplotcanvas.get_tk_widget().grid(row=0,column=0)
        self.zplottoolbar.grid(row=1,column=0)
        
        plt.close()
        

    def hist_equal(self):
        '''Methode zum Histogrammausgleich aller Slices'''
        
        
        popup = Toplevel()
        popup.attributes("-topmost", True)
        Label(popup, text="Histogrammausgleich...").grid(row=0,column=0)
        progress_var = DoubleVar()
        progress_bar = ttk.Progressbar(popup, variable=progress_var, maximum=self.n_frames)
        progress_bar.grid(row=1, column=0)
        popup.pack_slaves()    
        
         
        progress = 0
        progressstep = 1        
                
        try:
        
            for i in range(self.timestamps):
                for j in range(self.z_layers):
                    temp = self.origimages[i][j]
                    
                    eq = skimage.exposure.equalize_hist(temp)
                    eq = skimage.img_as_uint(eq)
                    
                    self.origimages[i][j] = eq
                    
                    pil = Image.fromarray(eq)
                    
                    pil = pil.convert("I")
    
                    pil = pil.point(lambda i: i*(1/255)).convert("RGB")
                    pil = pil.convert('L')
                    
                    self.pilimages[i][j] = pil
            
                    progress += progressstep
                    progress_var.set(progress)
                    popup.update()
            
            
            popup.destroy()
            self.update_img()
            self.draw_hist(self.origimages[self.t_index][self.z_index])           
                
            return
        except Exception as e:
            traceback.print_exc()
            m = "Fehler beim Histogramm-Ausgleich. " + str(e)
            tk.messagebox.showinfo(title="Fehler", message=m)
            popup.destroy()
            return    


            
    def hist_slice(self):
        '''Methode zum Slicing des Histogramms 
        anhand oberem und unterem Threshold fuer alle Slices'''
        
        try:
            lowervalue = simpledialog.askinteger("Input", "Untere Grenze:",parent = self.root)
            if not lowervalue:  # abort
                return
            uppervalue = simpledialog.askinteger("Input", "Obere Grenze:",parent = self.root)
            if not uppervalue:  # abort
                return
                
            popup = Toplevel()
            popup.attributes("-topmost", True)
            Label(popup, text="Slicing histograms...").grid(row=0,column=0)
            progress_var = DoubleVar()
            progress_bar = ttk.Progressbar(popup, variable=progress_var, maximum=self.n_frames)
            progress_bar.grid(row=1, column=0)#.pack(fill=tk.X, expand=1, side=tk.BOTTOM)
            popup.pack_slaves()    
            
                            
            progress = 0
            progressstep = 1    
            
            for i in range(self.timestamps):
                for j in range(self.z_layers):
                    temp = self.origimages[i][j]
                    
                    arr = np.array(temp)
                    arr = np.where(arr<lowervalue, 0,arr)
                    arr = np.where(arr>uppervalue, 0 , arr)
                    
                    self.origimages[i][j] = arr
                    
                    pil = Image.fromarray(arr)
                    
                    pil = pil.convert("I")
    
                    pil = pil.point(lambda i: i*(1/255)).convert("RGB")
                    pil = pil.convert('L')
                    
                    self.pilimages[i][j] = pil
                    
            
                    progress += progressstep
                    progress_var.set(progress)
                    #popup.update_idletasks()
                    popup.update()
            
            popup.destroy()
            self.update_img()
            self.draw_hist(self.origimages[self.t_index][self.z_index])           
            return  
        except Exception as e:
            traceback.print_exc()
            m = "Fehler beim Histogramm-Slicing. " + str(e)
            tk.messagebox.showinfo(title="Fehler", message=m)
            popup.destroy()
            return  
    
   
    def edit_bc(self):
          '''Methode zum Anpassen der Helligkeit und 
          linearem Kontrast fuer alle Slices'''
          try:
              brightnessvalue = simpledialog.askfloat("Input", "Helligkeit Faktor:",parent = self.root)
              
              if not brightnessvalue:  # abort
                  return
              
              contrastvalue = simpledialog.askfloat("Input", "Linearer Kontrast Alpha:",parent = self.root)
     
              if not contrastvalue:  # abort
                  return
                  
              popup = Toplevel()
              popup.attributes("-topmost", True)
              Label(popup, text="Passe Helligkeit und Kontrast an...").grid(row=0,column=0)
              progress_var = DoubleVar()
              progress_bar = ttk.Progressbar(popup, variable=progress_var, maximum=self.n_frames)
              progress_bar.grid(row=1, column=0)#.pack(fill=tk.X, expand=1, side=tk.BOTTOM)
              popup.pack_slaves()    
              
                              
              progress = 0
              progressstep = 1    
              
              for i in range(self.timestamps):
                  for j in range(self.z_layers):
                      img = self.origimages[i][j]
                      
                      temp = img*brightnessvalue
                      
                      '''Formel (19) Thesis'''
                      c= int(self.hist_bins/2)
                      temp = c + self.contrast_value*(temp-c)
                      temp = np.clip(temp,0,self.hist_bins).astype(img.dtype)
                      
                      
                      self.origimages[i][j] = temp
                      
                      pil = Image.fromarray(temp)
                      
                      pil = pil.convert("I")
      
                      pil = pil.point(lambda i: i*(1/255)).convert("RGB")
                      pil = pil.convert('L')
                      
                      self.pilimages[i][j] = pil
              
                      progress += progressstep
                      progress_var.set(progress)
           
                      popup.update()
              
              popup.destroy()
              self.update_img()
              self.draw_hist(self.origimages[self.t_index][self.z_index])           
              return  
          except Exception as e:
              traceback.print_exc()
              m = "Fehler beim Anpassen von Helligkeit und Kontrast. " + str(e)
              tk.messagebox.showinfo(title="Fehler", message=m)
              popup.destroy()
              return  
   
        
    def plastid_segmentation(self, image):

        eq = skimage.exposure.equalize_hist(image)
        
        '''Force Konvertierung auf 8Bit, weil 16Bit nicht kompatibel mit findContours()'''
        eq = skimage.img_as_ubyte(eq)
        
        
        k = self.num_clusters

        '''kmeans clustering'''
        pixel_values = eq.reshape((-1, 1)).astype(np.float32)
        _, labels, centers = cv2.kmeans(
            pixel_values, k, None, (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 100, 0.2), 10, cv2.KMEANS_RANDOM_CENTERS
        )
        segmented_image = labels.reshape(image.shape)
        
        '''Sortiere Cluster nach groesster Durchschnitts-Intensitaet'''
        cluster_properties = []
        for i in range(k):
            mask = (segmented_image == i).astype(np.uint8)
            cluster_intensity = np.mean(image[mask == 1])
            cluster_properties.append((i,cluster_intensity))
            
        cluster_properties.sort(key=lambda x: x[1],reverse=True)
           
        '''Temporaeres Bild erzeugen mit Pixelkoordinaten des hellsten Clusters'''
        brightest_cluster_label = cluster_properties[0][0]
        output_image = np.zeros_like(eq)
        output_image[segmented_image == brightest_cluster_label] = 255
            
        '''Closing mit 2x2 Kernel, um Rauschartefakte zu entfernen'''
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (2,2))

        output_image = cv2.morphologyEx(output_image,cv2.MORPH_CLOSE,kernel, iterations =1)
            
            
        '''Konturen der Patches ermitteln'''
        contours, _ = cv2.findContours(output_image, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
        plastid_coordinates = []
        for contour in contours:
            temp = np.zeros_like(eq)
            temp = cv2.drawContours(temp,contour,0,255,3)
              
            coords = np.column_stack(np.where(temp > 0))
            if len(coords) > 0:
                cy, cx = np.mean(coords, axis=0).astype(int)
                plastid_coordinates.append((cx, cy))
            else:
                cx, cy = -1, -1  # Kein gültiger Schwerpunkt
                
        return plastid_coordinates 
              
            
            
    def export(self):
        '''Methode zum Exportieren der ROIs'''
        try:
            rois = []
            
            files = [('ROI-Zip', '*.zip')]
            filepath = asksaveasfile(filetypes = files, defaultextension = '.zip',initialfile=os.path.splitext(os.path.basename(self.image_path))[0]+'.zip',parent = self.root)    
            
            if not filepath:  # abort
                return
            
            popup = Toplevel()
            popup.attributes("-topmost", True)
            Label(popup, text="Export...").grid(row=0,column=0)
            progress_var = DoubleVar()
            progress_bar = ttk.Progressbar(popup, variable=progress_var, maximum=self.n_frames)
            progress_bar.grid(row=1, column=0)#.pack(fill=tk.X, expand=1, side=tk.BOTTOM)
            popup.pack_slaves()
            
            progress = 0
            progressstep = 1    
            
            for i in range(self.timestamps):
                for j in range(self.z_layers):
                    coords = self.plastid_coords[i][j]
                    
                    count = 0
                    for c in coords:
                        x_min = int(c[0]-4)
                        y_min = int(c[1]-4)
                        
                        x_max = int(c[0]+4)
                        y_max = int(c[1]+4)
                        
                        count = count+1
                        
                        '''Roi mit Parametern versehen'''
                        roi_name = f"{i:04d}-{j:04d}-{count:04d}"
                        
                        roi = roifile.ImagejRoi()
                        
                        roi.top = y_min
                        roi.left = x_min
                        roi.bottom = y_max
                        roi.right = x_max
                        roi.name = roi_name
                        roi.c_position = 1
                        roi.t_position = i+1
                        roi.z_position = j
                        roi.roitype = roifile.ROI_TYPE.OVAL
                        
                      
                        rois.append((roi_name,roi))
                     
                    progress += progressstep
                    progress_var.set(progress)
          
                    popup.update()   
      
            for r in rois:
                r[1].tofile(filepath.name)
                   
            popup.destroy()
            m = "Speichern erfolgreich!"
            tk.messagebox.showinfo(title="Info", message=m)
            
            return    
        except Exception as e:
            traceback.print_exc()
            m = "Fehler Speichern der ROIs. " + str(e)
            tk.messagebox.showinfo(title="Fehler", message=m)
            popup.destroy()
            return  
    
    def edit_reset(self):
        '''Alle Bilder neu aus der Datei laden'''
        self.open_file(1)
        
    def edit_mode_off(self):
     
        self.plastide_edit_mode = False
        self.plastide_edit_label["text"] = "Edit Mode: Off"
        self.plastide_edit_label["fg"] = "black"
        return
        
    def toggle_edit_mode(self):
        state = str(self.plastide_edit_button['state'])
        if state == 'disabled':
            return
        if self.plastide_edit_mode:
            self.edit_mode_off()
            self.redraw_image()
            
        else:
            self.plastide_edit_mode = True
            self.plastide_edit_label["text"] = "Edit Mode: On"
            self.plastide_edit_label["fg"] = "green"
            
            self.redraw_image()
            
    '''
    =============================================================================
    Methoden zur Steuerung mit Maus-Cursor
    =============================================================================
    '''

    def mouse_down_left(self, event):
       '''Speichere Cursor-Koordinaten fuer Drag'''
       self.__old_event = event
       print(self.__old_event.x)
       print(self.__old_event.y)
       
       '''fuege Plastid hinzu, falls im Edit-Mode'''
       if self.plastide_edit_mode:
           
           self.plastid_coords[self.t_index][self.z_index].append((self.cursor_x,self.cursor_y))
           self.temp = self.temp.convert("RGBA")
           draw = ImageDraw.Draw(self.temp)
           
           x_min = int(self.cursor_x-4)
           y_min = int(self.cursor_y-4)
           
           x_max = int(self.cursor_x+4)
           y_max = int(self.cursor_y+4)
           
           draw.ellipse([x_min,y_min,x_max,y_max], outline="#00ff00")
           self.draw_plot()
           self.redraw_image()
           
    def mouse_down_right(self,event):
        print("right click")
        if self.plastide_edit_mode:
            x_min = int(self.cursor_x-4)
            y_min = int(self.cursor_y-4)
            
            x_max = int(self.cursor_x+4)
            y_max = int(self.cursor_y+4)
        
            coords = self.plastid_coords[self.t_index][self.z_index]
            
            indexes = []
            for i in range(len(coords)):
                if coords[i][0] in range(x_min,x_max) and coords[i][1] in range(y_min,y_max):
                    indexes.append(i)
            
            self.plastid_coords[self.t_index][self.z_index] = [i for j, i in enumerate(self.plastid_coords[self.t_index][self.z_index]) if j not in indexes]
    
            
            self.temp = self.pilimages[self.t_index][self.z_index]
            self.temp = self.apply_filters(self.temp)
            self.draw_plastid_ellipse()
            if self.draw_detections:
                self.draw_yolo()
            self.draw_image()
            self.draw_plot()
        
        return
   
    def mouse_move_left(self, event):
       '''Methode fuer Drag'''
       
       if not self.plastide_edit_mode:
           if (self.current_img == 0):
               return
           self.translate(event.x - self.__old_event.x, event.y - self.__old_event.y)
           self.redraw_image() 
           self.__old_event = event
    
    def mouse_move(self, event):
       '''
       Update der Koordinaten des Cursors im xylabel

       '''
       if (self.current_img == 0):
           return

       image_point = self.to_image_point(event.x, event.y)
       
       
       temp = self.origimages[self.t_index][self.z_index]

       
       
       
       if len(image_point) != 0:
           self.cursor_x = int(image_point[0])
           self.cursor_y = int(image_point[1])
           self.xylabel["text"] = (f"({int(image_point[0])}, {int(image_point[1])}), Value {temp[int(image_point[1]),int(image_point[0])]}")
       else:
   
           self.xylabel["text"] = ("(--, --)")    


    def to_image_point(self, x, y):
        '''Mouse-Event in Bildkoordinaten umwandeln'''
        if self.current_img == 0:
            return []

        mat_inv = np.linalg.inv(self.mat_affine)
        image_point = np.dot(mat_inv, (x, y, 1.))
        if  image_point[0] < 0 or image_point[1] < 0 or image_point[0] > self.temp.width or image_point[1] > self.temp.height:
            return []

        return image_point
    
    def scale_at(self, scale:float, cx:float, cy:float):
       '''Skalierung mit Cursor als Zentrum'''
       self.translate(-cx, -cy)
       self.scale(scale)
       self.translate(cx, cy)    
       
    def mouse_wheel_linux(self, event):
        if self.current_img == 0:
            return

        '''Zoom/skalierung bei Linux'''
        if event.num == 4:
            print("mwheelup")
            self.scale_at(1.25, event.x, event.y)
        elif event.num == 5:
            print("mwheeldown")
            self.scale_at(0.8, event.x, event.y)
    
    def mouse_wheel(self, event):
       '''Zoom/Skalierung per Mausrad'''
       if self.current_img == 0:
           return

       if event.state != 9: 
           if (event.delta > 0):
       
               self.scale_at(1.25, event.x, event.y)
           else:
 
               self.scale_at(0.8, event.x, event.y)
  
       self.redraw_image()
        
    def mouse_double_click_left(self, event):
        '''Zoom und Drag zuruecksetzen bei Doppelklick auf Canvas'''
        if self.current_img == 0:
            return
        self.reset_zoom(self.temp.width, self.temp.height)
        self.redraw_image() 

    def reset_transform(self):
        '''Setzt die Transformationsmatrix auf Einheitsmatrix zurueck'''
        self.mat_affine = np.eye(3) 
    
    def translate(self, offset_x, offset_y):
        '''Translation'''
        mat = np.eye(3) 
        mat[0, 2] = float(offset_x)
        mat[1, 2] = float(offset_y)
        self.mat_affine = np.dot(mat, self.mat_affine)
       
    def scale(self, scale:float):
        '''Skalierung'''
        mat = np.eye(3) 
        mat[0, 0] = scale
        mat[1, 1] = scale

        self.mat_affine = np.dot(mat, self.mat_affine)
        
 
    def redraw_image(self):
        '''draw ohne update'''
        if self.current_img == 0:
            return
        self.draw_image()



    '''
    =============================================================================
    Methoden zur Veraenderung der Ansicht bei Klick der Schaltflaeche
    =============================================================================
    '''
    
    def reset_view(self):
        self.brightness_value = 1
        self.contrast_value = 1
        self.yolo_threshold = 0.5
        self.update_img()
        self.label_contrast["text"] =(f"Contrast: {self.contrast_value:.1f}")
        self.label_thresh["text"] =(f"Yolo Threshold: {self.yolo_threshold:.1f}")
        self.label_brightness["text"] =(f"Brightness: {self.brightness_value:.1f}")
        
        
            
    def contrast_up(self):
        if self.contrast_value < 4.9:
            self.contrast_value += 0.1
            print(self.contrast_value)
            self.update_img()
            self.label_contrast["text"] =(f"Contrast: {self.contrast_value:.1f}")
        else:
            return
        
    
    def contrast_down(self):
        if self.contrast_value > 0.1:
            self.contrast_value -= 0.1
            print(self.contrast_value)
            self.update_img()
            self.label_contrast["text"] =(f"Contrast: {self.contrast_value:.1f}")
        else:
            return
    
    def thresh_down(self):
        if self.yolo_threshold > 0.1:
            self.yolo_threshold  -= 0.1
            print(self.yolo_threshold )
            self.update_img()
            self.label_thresh["text"] =(f"Yolo Threshold: {self.yolo_threshold:.1f}")
            
        else:
            return
    
    def thresh_up(self):
        if self.yolo_threshold < 0.9:
            self.yolo_threshold += 0.1
            print(self.yolo_threshold)
            self.update_img()
            self.label_thresh["text"] =(f"Yolo Threshold: {self.yolo_threshold:.1f}")
        else:
            return    
    
    def brightness_up(self):
        if self.brightness_value < 4.9:
            self.brightness_value += 0.1
            print(self.brightness_value)
            self.update_img()
            self.label_brightness["text"] =(f"Brightness: {self.brightness_value:.1f}")
        else:
            return
        

    
    def brightness_down(self):
        if self.brightness_value > 0.1:
            self.brightness_value -= 0.1
            print(self.brightness_value)
            self.update_img()
            self.label_brightness["text"] =(f"Brightness: {self.brightness_value:.1f}")
        else:
            return
    
    '''
    =============================================================================
    Methoden zur Navigation durch den Stack
    =============================================================================
    '''
    
    
    def z_prev(self):
        if self.z_index > 0:
            
            self.edit_mode_off()
            self.z_index -= 1
            print(self.z_index)
            self.update_img()
            self.draw_hist(self.origimages[self.t_index][self.z_index])
        else:
            return
        
    def z_next(self):
        if self.z_index < self.z_layers-1:
            self.edit_mode_off()
            self.z_index += 1
            print(self.z_index)
            self.update_img()
            self.draw_hist(self.origimages[self.t_index][self.z_index])
        else:
            return
        
        
    def t_prev(self):
          if self.t_index > 0:
              self.edit_mode_off()
              self.t_index -= 1
              print(self.t_index)
              self.update_img()
              self.draw_hist(self.origimages[self.t_index][self.z_index])
              
              if self.model != 0:
                  
                  self.draw_plot()
          else:
              print(self.t_index)
              return
          
    def t_next(self):
          if self.t_index < self.timestamps-1:
              self.edit_mode_off()
              self.t_index += 1
              print(self.t_index)
              self.update_img()
              self.draw_hist(self.origimages[self.t_index][self.z_index])
              
              if self.model != 0:
                  
                  self.draw_plot()
          else:
              print(self.t_index)
              return
    '''
    =============================================================================
    
    =============================================================================
    '''




if __name__ == "__main__":
    
    root = Tk()
    viewer = HyperstackViewer(root)
