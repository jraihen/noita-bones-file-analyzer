import tkinter as tk
from tkinter import filedialog, messagebox
import xml.etree.ElementTree as ET
import os
import sys
import json
import subprocess
import platform
import traceback
import re
from PIL import Image, ImageTk

def get_resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

class ToolTip:
    def __init__(self, widget, text):
        self.widget = widget
        self.text = text
        self.tipwindow = None
        self.id = None
        self.x = self.y = 0
        self.widget.bind("<Enter>", self.enter)
        self.widget.bind("<Leave>", self.leave)

    def enter(self, event=None):
        self.schedule()

    def leave(self, event=None):
        self.unschedule()
        self.hidetip()

    def schedule(self):
        self.unschedule()
        self.id = self.widget.after(300, self.showtip)

    def unschedule(self):
        id = self.id
        self.id = None
        if id:
            self.widget.after_cancel(id)

    def showtip(self, event=None):
        x, y, cx, cy = self.widget.bbox("insert")
        x = x + self.widget.winfo_rootx() + 25
        y = y + cy + self.widget.winfo_rooty() + 25
        self.tipwindow = tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(True)
        tw.wm_geometry("+%d+%d" % (x, y))
        label = tk.Label(tw, text=self.text, justify=tk.LEFT,
                         background="#2a2a2a", foreground="white", relief=tk.SOLID, borderwidth=1,
                         font=("Courier", "10", "normal"))
        label.pack(ipadx=3, ipady=1)

    def hidetip(self):
        tw = self.tipwindow
        self.tipwindow = None
        if tw:
            tw.destroy()

class WandParserApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Noita Wand Analyzer")
        self.root.geometry("800x550")
        self.root.configure(bg="#121212")

        if platform.system() == 'Windows':
            app_data_dir = os.path.join(os.environ.get('APPDATA', os.path.expanduser("~")), 'NoitaWandAnalyzer')
        else:
            app_data_dir = os.path.join(os.path.expanduser("~"), '.noita_wand_analyzer')
        
        os.makedirs(app_data_dir, exist_ok=True)
        self.config_file = os.path.join(app_data_dir, 'config.json')

        self.data_path = get_resource_path("data")
        self.last_bone_dir = ""
        self.file_paths = {}
        self.image_refs = []

        self.load_config()

        self.left_frame = tk.Frame(root, width=200, bg="#121212")
        self.left_frame.pack(side=tk.LEFT, fill=tk.Y, padx=10, pady=10)

        self.btn_load = tk.Button(self.left_frame, text="Select Bone Files", command=self.load_files)
        self.btn_load.pack(fill=tk.X)

        self.btn_delete = tk.Button(self.left_frame, text="Delete Bone File", command=self.delete_file, bg="#5a1919", fg="#d3d3d3")
        self.btn_delete.pack(fill=tk.X, pady=(5, 0))

        self.btn_refresh = tk.Button(self.left_frame, text="Refresh List (F5)", command=self.refresh_files)
        self.btn_refresh.pack(fill=tk.X, pady=(5, 0))

        self.listbox = tk.Listbox(self.left_frame, bg="#1e1e1e", fg="white", selectbackground="#4a4a4a")
        self.listbox.pack(fill=tk.BOTH, expand=True, pady=5)
        self.listbox.bind('<<ListboxSelect>>', self.on_select)
        self.listbox.bind('<Double-Button-1>', self.on_double_click)
        self.listbox.bind('<Return>', self.on_double_click)
        self.listbox.bind('<Delete>', self.delete_file)

        self.root.bind('<F5>', self.refresh_files)

        self.right_frame = tk.Frame(root, bg="#121212")
        self.right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=10, pady=10)

        self.bottom_right = tk.Frame(self.right_frame, bg="#121212")
        self.bottom_right.pack(side=tk.BOTTOM, fill=tk.X, pady=10)

        self.top_right = tk.Frame(self.right_frame, bg="#121212")
        self.top_right.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        self.lbl_wand_img = tk.Label(self.top_right, bg="#121212")
        self.lbl_wand_img.pack(side=tk.LEFT, padx=30)

        self.text_info = tk.Text(self.top_right, state=tk.DISABLED, font=("Courier", 10, "bold"), bg="#121212", fg="#d3d3d3", bd=0)
        self.text_info.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.auto_load_bone_files()

    def load_config(self):
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    self.last_bone_dir = config.get("last_bone_dir", "")
            except Exception:
                pass

    def save_config(self):
        config = {
            "last_bone_dir": self.last_bone_dir
        }
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=4)
        except Exception:
            pass

    def auto_load_bone_files(self):
        if self.last_bone_dir and os.path.isdir(self.last_bone_dir):
            try:
                files_with_time = []
                for filename in os.listdir(self.last_bone_dir):
                    if filename.endswith('.xml') or filename.endswith('.bone'):
                        filepath = os.path.join(self.last_bone_dir, filename)
                        files_with_time.append((filename, os.path.getmtime(filepath), filepath))
                
                files_with_time.sort(key=lambda x: x[1], reverse=True)
                
                for filename, _, filepath in files_with_time:
                    if filename not in self.file_paths:
                        self.file_paths[filename] = filepath
                        self.listbox.insert(tk.END, filename)
            except Exception:
                pass

    def load_files(self):
        initial_dir = self.last_bone_dir if os.path.isdir(self.last_bone_dir) else "/"
        files = filedialog.askopenfilenames(
            title="Select Bone Files",
            initialdir=initial_dir,
            filetypes=[("XML / Bone files", "*.xml *.bone"), ("All files", "*.*")]
        )
        if files:
            self.last_bone_dir = os.path.dirname(files[0])
            self.save_config()
            self.refresh_files()

    def delete_file(self, event=None):
        selection = self.listbox.curselection()
        if not selection:
            return
        
        index = selection[0]
        filename = self.listbox.get(index)
        filepath = self.file_paths.get(filename)

        if filepath and os.path.exists(filepath):
            if messagebox.askyesno("Delete File", f"Are you sure you want to permanently delete the original file '{filename}' from the disk?\n(This action cannot be undone.)"):
                try:
                    os.remove(filepath)
                    self.listbox.delete(index)
                    del self.file_paths[filename]
                    self.clear_ui()
                    self.update_text(f"'{filename}' has been deleted.")
                except Exception as e:
                    messagebox.showerror("Error", f"Failed to delete file:\n{e}")

    def refresh_files(self, event=None):
        self.listbox.delete(0, tk.END)
        self.file_paths.clear()
        self.clear_ui()
        self.auto_load_bone_files()

    def on_select(self, event):
        selection = event.widget.curselection()
        if selection:
            index = selection[0]
            filename = event.widget.get(index)
            filepath = self.file_paths[filename]
            self.parse_and_display(filepath)

    def on_double_click(self, event):
        selection = self.listbox.curselection()
        if selection:
            index = selection[0]
            filename = self.listbox.get(index)
            filepath = self.file_paths[filename]
            
            if platform.system() == 'Windows':
                os.startfile(filepath)
            elif platform.system() == 'Darwin':
                subprocess.call(('open', filepath))
            else:
                subprocess.call(('xdg-open', filepath))

    def clear_ui(self):
        for widget in self.bottom_right.winfo_children():
            widget.destroy()
        self.lbl_wand_img.config(image='')
        self.image_refs.clear()

    def parse_xml_safe(self, filepath):
        with open(filepath, 'r', encoding='utf-8-sig', errors='ignore') as f:
            content = f.read()
        
        content = content.replace('\x00', '')
        content = re.sub(r'[^\x09\x0A\x0D\x20-\uD7FF\uE000-\uFFFD\U00010000-\U0010FFFF]', '', content)
        
        start_idx = content.find('<')
        if start_idx != -1:
            content = content[start_idx:]
            
        return ET.fromstring(content)

    def resolve_image_path(self, xml_img_path):
        if not xml_img_path:
            return ""
        rel_path = xml_img_path.replace("data/", "", 1) if xml_img_path.startswith("data/") else xml_img_path
        full_path = os.path.join(self.data_path, rel_path)
        
        if full_path.endswith('.xml') and os.path.exists(full_path):
            try:
                root = self.parse_xml_safe(full_path)
                real_file = root.get('filename', '')
                if real_file:
                    rel_path = real_file.replace("data/", "", 1) if real_file.startswith("data/") else real_file
                    full_path = os.path.join(self.data_path, rel_path)
            except:
                pass
        return full_path

    def parse_and_display(self, filepath):
        self.clear_ui()
        
        try:
            root = self.parse_xml_safe(filepath)

            ability = root.find('AbilityComponent')
            if ability is None:
                self.update_text("The wand data (AbilityComponent) does not exist in the file.")
                return

            gun_config = ability.find('gun_config')
            gunaction_config = ability.find('gunaction_config')

            mana_max = float(ability.get('mana_max', '0'))
            mana_chg_spd = float(ability.get('mana_charge_speed', '0'))
            shuffle = "Yes" if gun_config.get('shuffle_deck_when_empty', '0') == '1' else "No"
            spells_per_cast = gun_config.get('actions_per_round', '1')
            capacity = int(gun_config.get('deck_capacity', '0'))
            
            cast_delay = float(gunaction_config.get('fire_rate_wait', '0')) / 60.0
            rechrg_time = float(gun_config.get('reload_time', '0')) / 60.0
            spread = float(gunaction_config.get('spread_degrees', '0'))
            speed = float(gunaction_config.get('speed_multiplier', '1.0'))

            if self.data_path and os.path.exists(self.data_path):
                for sprite in root.findall('SpriteComponent'):
                    if 'item' in sprite.get('_tags', ''):
                        raw_path = sprite.get('image_file', '')
                        full_wand_path = self.resolve_image_path(raw_path)
                        
                        if os.path.exists(full_wand_path) and full_wand_path.endswith('.png'):
                            try:
                                img = Image.open(full_wand_path).convert("RGBA")
                                img = img.resize((img.width * 3, img.height * 3), Image.NEAREST)
                                photo = ImageTk.PhotoImage(img)
                                self.lbl_wand_img.config(image=photo)
                                self.image_refs.append(photo)
                            except Exception:
                                pass
                        break

            always_casts = []
            parsed_spells = []
            
            for child in root.findall('Entity'):
                action_comp = child.find('ItemActionComponent')
                item_comp = child.find('ItemComponent')
                if action_comp is not None and item_comp is not None:
                    slot = int(item_comp.get('inventory_slot.x', '0'))
                    action_id = action_comp.get('action_id', 'Unknown')
                    is_always_cast = item_comp.get('permanently_attached', '0') == '1'
                    
                    spell_img_path = ""
                    for sprite in child.findall('SpriteComponent'):
                        img_file = sprite.get('image_file', '')
                        tags = sprite.get('_tags', '')
                        if 'item_identified' in tags and img_file:
                            spell_img_path = img_file
                            break
                        elif 'gun_actions' in img_file:
                            spell_img_path = img_file
                    
                    spell_data = {'slot': slot, 'img': spell_img_path, 'id': action_id}
                    if is_always_cast:
                        always_casts.append(spell_data)
                    else:
                        parsed_spells.append(spell_data)

            arranged_spells = [None] * capacity
            for ps in parsed_spells:
                preferred_slot = ps['slot']
                if 0 <= preferred_slot < capacity and arranged_spells[preferred_slot] is None:
                    arranged_spells[preferred_slot] = ps
                else:
                    for i in range(capacity):
                        if arranged_spells[i] is None:
                            arranged_spells[i] = ps
                            break

            if self.data_path and os.path.exists(self.data_path):
                if always_casts:
                    ac_container = tk.Frame(self.bottom_right, bg="#121212")
                    ac_container.pack(fill=tk.X, pady=(0, 10))
                    
                    ac_lbl = tk.Label(ac_container, text="Always Cast", fg="#4a90e2", bg="#121212", font=("Courier", 10, "bold"))
                    ac_lbl.pack(anchor=tk.W, padx=5)
                    
                    ac_slot_frame = tk.Frame(ac_container, bg="#121212")
                    ac_slot_frame.pack(anchor=tk.W, padx=5)
                    
                    for idx, ac_spell in enumerate(always_casts):
                        slot_frame = tk.Frame(ac_slot_frame, width=36, height=36, bg="#1e1e1e", highlightbackground="#4a90e2", highlightthickness=1)
                        slot_frame.grid_propagate(False)
                        slot_frame.grid(row=0, column=idx, padx=2, pady=2)
                        
                        if ac_spell['img']:
                            full_spell_path = self.resolve_image_path(ac_spell['img'])
                            if os.path.exists(full_spell_path) and full_spell_path.endswith('.png'):
                                try:
                                    img = Image.open(full_spell_path).convert("RGBA")
                                    img = img.resize((img.width * 2, img.height * 2), Image.NEAREST)
                                    photo = ImageTk.PhotoImage(img)
                                    lbl = tk.Label(slot_frame, image=photo, bg="#1e1e1e", bd=0)
                                    lbl.pack(expand=True)
                                    self.image_refs.append(photo)
                                    ToolTip(lbl, ac_spell['id'])
                                except Exception:
                                    pass

                spells_container = tk.Frame(self.bottom_right, bg="#121212")
                spells_container.pack(fill=tk.X)

                max_cols = 13 
                for i in range(capacity):
                    row = i // max_cols
                    col = i % max_cols
                    
                    slot_frame = tk.Frame(spells_container, width=36, height=36, bg="#1e1e1e", highlightbackground="#333333", highlightthickness=1)
                    slot_frame.grid_propagate(False)
                    slot_frame.grid(row=row, column=col, padx=2, pady=2)

                    spell_in_slot = arranged_spells[i]
                    
                    if spell_in_slot and spell_in_slot['img']:
                        full_spell_path = self.resolve_image_path(spell_in_slot['img'])
                        if os.path.exists(full_spell_path) and full_spell_path.endswith('.png'):
                            try:
                                img = Image.open(full_spell_path).convert("RGBA")
                                img = img.resize((img.width * 2, img.height * 2), Image.NEAREST)
                                photo = ImageTk.PhotoImage(img)
                                lbl = tk.Label(slot_frame, image=photo, bg="#1e1e1e", bd=0)
                                lbl.pack(expand=True)
                                self.image_refs.append(photo)
                                ToolTip(lbl, spell_in_slot['id'])
                            except Exception:
                                pass

            info = (
                f"Shuffle          {shuffle}\n"
                f"Spells/Cast      {spells_per_cast}\n"
                f"Cast delay       {cast_delay:.2f}s\n"
                f"Rechrg. Time     {rechrg_time:.2f}s\n"
                f"Mana max         {mana_max:.0f}\n"
                f"Mana chg. Spd    {mana_chg_spd:.0f}\n"
                f"Capacity         {capacity}\n"
                f"Spread           {spread:.1f}°\n"
                f"Speed            {speed:.2f}x\n"
            )
            self.update_text(info)

        except Exception as e:
            error_msg = f"[ ERROR OCCURRED ]\nFile: {os.path.basename(filepath)}\nMsg: {str(e)}\n\n[ TRACEBACK ]\n{traceback.format_exc()}"
            self.update_text(error_msg)

    def update_text(self, text):
        self.text_info.config(state=tk.NORMAL)
        self.text_info.delete('1.0', tk.END)
        self.text_info.insert(tk.END, text)
        self.text_info.config(state=tk.DISABLED)

if __name__ == "__main__":
    root = tk.Tk()
    app = WandParserApp(root)
    root.mainloop()