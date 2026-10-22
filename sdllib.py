import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog
from tkinter.ttk import Button, Frame
import os
import re
import sqlite3
import csv
from datetime import datetime
import sys
from xml.etree import ElementTree as ET # For basic XML structure for TMX output

# For robust XPath and Access DB interaction (see notes below)
try:
    from lxml import etree as LXET # For better XPath support
except ImportError:
    LXET = None
    print("Warning: lxml not found. SDLTB conversion will rely on basic ElementTree XPath, which may be less robust.")
    print("Consider installing lxml for full XPath support: pip install lxml")

try:
    import pyodbc # For connecting to Access databases (.sdltb files)
except ImportError:
    pyodbc = None
    print("Warning: pyodbc not found. SDLTB conversion functionality will be limited.")
    print("On Windows, install pyodbc (pip install pyodbc) and ensure Access Database Engine is installed.")
    print("On Linux/macOS, pyodbc requires specific ODBC drivers for MDB files, which are complex to set up.")


# Replicating core data structures from Java for Termbase processing
class Term:
    """Represents a term within a termgroup."""
    def __init__(self, newword):
        self.word = newword
        self.termInfo = ""
        self.usage = ""

    def addTermInfo(self, i):
        self.termInfo += i

    def getTermInfo(self):
        return self.termInfo

    def addUsage(self, u):
        self.usage = u

    def getUsage(self):
        return self.usage

    def getWord(self):
        return self.word

class Termgroup:
    """Represents a group of terms for a specific language within a concept."""
    def __init__(self):
        self.terms = []
        self.definition = ""

    def addTerm(self, term):
        self.terms.append(term)

    def addDefinition(self, def_str):
        self.definition = def_str

    def getDefinition(self):
        return self.definition

class Concept:
    """Represents a concept, holding termgroups for different languages and metadata."""
    def __init__(self):
        self.termgroups = {} # Maps language (str) to Termgroup object
        self.creator = ""
        self.creationTime = ""
        self.modifier = ""
        self.modificationTime = ""
        self.metaData = {} # Maps metadata key (str) to value (str)

    def setEntryCreator(self, c):
        self.creator = c

    def getCreator(self):
        return self.creator

    def setCreationTime(self, t):
        self.creationTime = t

    def getCreationTime(self):
        return self.creationTime

    def setEntryModifier(self, m):
        self.modifier = m

    def getModifier(self):
        return self.modifier

    def setModificationTime(self, t):
        self.modificationTime = t

    def getModificationTime(self):
        return self.modificationTime

    def addTerm(self, term, lang):
        if lang in self.termgroups:
            self.termgroups[lang].addTerm(term)

    def addTermgroup(self, lang):
        if lang not in self.termgroups:
            self.termgroups[lang] = Termgroup()

    def addDef(self, def_str, lang):
        if lang in self.termgroups:
            self.termgroups[lang].addDefinition(def_str)

    def addMeta(self, key, value):
        self.metaData[key] = value

    def getMeta(self, key):
        return self.metaData.get(key, "")

class Termbase:
    """Represents the entire termbase, holding multiple concepts and language information."""
    def __init__(self):
        self.conceptList = {} # Maps concept ID (int) to Concept object
        self.languageList = {} # Maps language name (str) to max number of terms for that language
        self.conceptMetaList = [] # List of unique concept-level metadata types (str)

    def addConcept(self, key):
        self.conceptList[key] = Concept()

    def inLanguageList(self, name):
        # Returns the max number of terms for a language, or 0 if not present.
        return self.languageList.get(name, 0)

    def addLanguage(self, name):
        # This method in Java initially put 1, then setMaxNumber updated it.
        # For simplicity, we ensure it exists or `setMaxNumber` will add/update.
        if name not in self.languageList:
            self.languageList[name] = 1 # Initial value as per Java

    def setMaxNumber(self, name, number):
        self.languageList[name] = number

    def getMaxNumber(self, name):
        return self.languageList.get(name, 0)

    def inMeta(self, s):
        if s not in self.conceptMetaList:
            self.conceptMetaList.append(s)

# Main GUI application class
class SDLConverter(tk.Tk):
    """
    GUI application to convert SDL Trados Studio resource files.
    Supports converting SDLTM to TMX and SDLTB to CSV/TXT.
    """
    def __init__(self):
        super().__init__()
        self.title("SDL Trados Studio Resource Converter")
        self.geometry("250x300")
        self.resizable(False, False)
        self.create_widgets()

    def create_widgets(self):
        """Creates and packs the GUI buttons."""
        frame = Frame(self)
        frame.pack(pady=10)

        self.button_sdltm2tmx = Button(frame, text="Convert SDLTM",
                                       command=self.convert_sdltm_action)
        self.button_sdltm2tmx.config(width=25, height=2)
        self.button_sdltm2tmx.pack(pady=5)

        self.button_sdltb2csv = Button(frame, text="Convert SDLTB",
                                       command=self.convert_sdltb_action)
        self.button_sdltb2csv.config(width=25, height=2)
        self.button_sdltb2csv.pack(pady=5)

    def show_message(self, title, message, is_error=False):
        """Displays an information or error message box."""
        if is_error:
            messagebox.showerror(title, message)
        else:
            messagebox.showinfo(title, message)

    def convert_sdltm_action(self):
        """Action handler for the 'Convert SDLTM' button."""
        self.get_tm()

    def convert_sdltb_action(self):
        """Action handler for the 'Convert SDLTB' button."""
        self.convert_tb()

    def write_csv_row(self, writer, data_list, delimiter):
        """
        Writes a row to a CSV/TXT file, handling delimiters and quoting
        similar to the original Java logic.
        """
        if delimiter == "\t":
            # For tab-separated, Java wrote directly without quoting.
            writer.write(delimiter.join(map(str, data_list)) + '\n')
        else:
            # For other delimiters, use csv.writer to handle quoting.
            # Using StringIO to format the row before writing to the main file object.
            import io
            temp_output = io.StringIO()
            csv_writer = csv.writer(temp_output, delimiter=delimiter, quotechar='"', quoting=csv.QUOTE_MINIMAL)
            csv_writer.writerow(data_list)
            writer.write(temp_output.getvalue())

    def get_tm(self):
        """Opens a file dialog for SDLTM files and initiates conversion."""
        files = filedialog.askopenfilenames(
            parent=self,
            title="Select SDLTM files",
            filetypes=[("SDLTM files", "*.sdltm")],
            multiple=True
        )
        if files:
            self.converttm(list(files))

    def converttm(self, files):
        """
        Converts SDL Trados Studio Translation Memory files (.sdltm) to TMX format.
        SDLTM files are treated as SQLite databases.
        The segment processing uses regex as in the original Java, acknowledging
        the original Java's TODO to improve XML parsing.
        """
        output_file_path = None
        if len(files) == 1:
            base_name = os.path.basename(files)
            output_file_path = os.path.join(os.path.dirname(files), os.path.splitext(base_name) + ".tmx")
        else:
            output_file_path = os.path.join(os.path.dirname(files), "converted.tmx")

        # Regular expressions copied from Java. Their effectiveness depends on SDLTM's internal XML structure. [7, 9]
        seg_pattern = re.compile(r"(.*?)(.*?)", re.DOTALL)
        # Note: The original Java `valueTextPattern` was `|`, which effectively matches nothing or empty string.
        # This regex will not remove any content.
        value_text_pattern = re.compile(r"|")
        start_tag_pattern = re.compile(r"Start(\d+)(\d+)(.*?).*?")
        end_tag_pattern = re.compile(r"End(\d+)\d+.*?")
        placeholder_pattern = re.compile(r".*?\d+(\d+)(.*?).*?", re.DOTALL)

        src_lang = ""
        tus_converted = 0

        try:
            # Determine source language from the first file. [7, 10]
            conn = sqlite3.connect(files)
            cursor = conn.cursor()
            cursor.execute("SELECT source_segment FROM translation_units LIMIT 1;")
            first_source_segment_row = cursor.fetchone()
            if first_source_segment_row:
                source_segment = first_source_segment_row
                seg_matcher = seg_pattern.search(source_segment)
                if seg_matcher and len(seg_matcher.groups()) >= 2:
                    src_lang = seg_matcher.group(2) # [10]
                else:
                    self.show_message("Error", "Could not determine source language. Using 'UNKNOWN'.")
                    src_lang = "UNKNOWN"
            cursor.close()
            conn.close()

            with open(output_file_path, 'w', encoding='utf-8') as out:
                # Constructing proper TMX XML using ElementTree, improving on Java's string concat. [10, 11]
                tmx_root = ET.Element("tmx", version="1.4")
                header = ET.SubElement(tmx_root, "header",
                                       {"creationtool": "SDLConverter",
                                        "creationtoolversion": "1.0",
                                        "datatype": "plaintext",
                                        "segtype": "sentence",
                                        "adminlang": "en-US",
                                        "srclang": src_lang,
                                        "o-tmf": "SDL Trados Studio"})
                ET.SubElement(header, "prop", type="TRADOS.GlobalTerminology").text = "0"
                body = ET.SubElement(tmx_root, "body")

                for file_path in files: # [12]
                    conn = sqlite3.connect(file_path)
                    cursor = conn.cursor()
                    cursor.execute("SELECT source_segment, target_segment, creation_date, creation_user, change_date, change_user, last_used_date, usage_counter FROM translation_units;")

                    for row in cursor: # [12]
                        source_segment_raw, target_segment_raw, creation_date, creation_user, change_date, change_user, last_used_date, usage_counter = row

                        # Process source segment with regex [13]
                        source_segment = seg_pattern.sub(r" \n $1\n ", source_segment_raw, 1)
                        source_segment = value_text_pattern.sub("", source_segment)
                        source_segment = start_tag_pattern.sub("", source_segment)
                        source_segment = end_tag_pattern.sub("", source_segment)
                        source_segment = placeholder_pattern.sub("", source_segment)
                        source_segment = source_segment.strip()

                        # Process target segment with regex [14]
                        target_segment = seg_pattern.sub(r" \n $1\n \n ", target_segment_raw, 1)
                        target_segment = value_text_pattern.sub("", target_segment)
                        target_segment = start_tag_pattern.sub("", target_segment)
                        target_segment = end_tag_pattern.sub("", target_segment)
                        target_segment = placeholder_pattern.sub("", target_segment)
                        target_segment = target_segment.strip()

                        # Assemble TMX translation unit [11]
                        tu_element = ET.SubElement(body, "tu",
                                                   {"creationdate": self._format_date_for_tmx(creation_date),
                                                    "creationid": creation_user or "",
                                                    "changedate": self._format_date_for_tmx(change_date),
                                                    "changeid": change_user or "",
                                                    "lastusagedate": self._format_date_for_tmx(last_used_date),
                                                    "usagecount": str(usage_counter or 0)})

                        tuv_src = ET.SubElement(tu_element, "tuv", {"xml:lang": src_lang})
                        seg_src = ET.SubElement(tuv_src, "seg")
                        seg_src.text = source_segment

                        # The original Java code did not explicitly determine the target language.
                        # For a valid TMX, a target language is needed. This Python version uses a placeholder.
                        tuv_target = ET.SubElement(tu_element, "tuv", {"xml:lang": "UNKNOWN_TARGET"})
                        seg_target = ET.SubElement(tuv_target, "seg")
                        seg_target.text = target_segment

                        tus_converted += 1
                    cursor.close()
                    conn.close()

                # Write the complete TMX XML tree to file.
                tmx_tree = ET.ElementTree(tmx_root)
                # Using lxml's pretty_print if available for better formatting.
                out.write(ET.tostring(tmx_root, encoding='utf-8', pretty_print=True).decode('utf-8'))

            self.show_message("Conversion Complete", f"{tus_converted} translation units converted to TMX.")

        except sqlite3.Error as e: # [15]
            self.show_message("Database Error", f"SQLite error: {e}. Input file may be empty or corrupted.", is_error=True)
        except IOError as e: # [15]
            self.show_message("File Error", f"IOException: {e}", is_error=True)
        except Exception as e: # Catch other potential errors [15]
            self.show_message("Error", f"An unexpected error occurred: {e}", is_error=True)

    def _format_date_for_tmx(self, date_str):
        """Helper to format dates from SQLite 'YYYY-MM-DD HH:MM:SS' to TMX 'YYYYMMDDTHHMMSSZ'."""
        if not date_str:
            return ""
        try:
            dt_obj = datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S")
            return dt_obj.strftime("%Y%m%dT%H%M%SZ")
        except ValueError:
            return date_str # Return original if parsing fails

    def convert_tb(self):
        """
        Converts SDL Trados Studio Termbase files (.sdltb) to CSV or TXT format.
        Requires pyodbc for Access database interaction and lxml for robust XPath.
        """
        if pyodbc is None:
            messagebox.showerror("Error", "pyodbc library not found. Cannot convert SDLTB files without it.\n"
                                 "Please install pyodbc (pip install pyodbc) and ensure Access Database Engine is installed on Windows.")
            return
        if LXET is None:
             messagebox.showwarning("Warning", "lxml library not found. SDLTB conversion will use basic ElementTree XPath, which may be less robust.\n"
                                  "Consider installing lxml for full XPath support: pip install lxml")

        files = filedialog.askopenfilenames(
            parent=self,
            title="Select SDLTB files",
            filetypes=[("SDLTB files", "*.sdltb")],
            multiple=True
        )
        if not files:
            return

        delimiter_options = ["Comma-separated CSV", "Semicolon-separated CSV", "Tab-separated TXT"]
        output_type = simpledialog.askstring("Output Type", "Please select the output type:",
                                            initialvalue=delimiter_options,
                                            parent=self,
                                            menu=delimiter_options) # [16]

        delimiter = ","
        if output_type == "Comma-separated CSV":
            delimiter = ","
        elif output_type == "Semicolon-separated CSV":
            delimiter = ";"
        elif output_type == "Tab-separated TXT": # [17]
            delimiter = "\t"
        else:
            return # User cancelled

        synonym_options = ["Separate columns", "Separated by a pipe (|)"]
        synonyms_presentation = simpledialog.askstring("Synonym Presentation", "Please select how synonyms should be presented:",
                                                    initialvalue=synonym_options,
                                                    parent=self,
                                                    menu=synonym_options) # [17]
        if synonyms_presentation is None:
            return # User cancelled

        # Determine output file path [18]
        root_dir = os.path.dirname(files)
        output_file_name = "converted.txt" if delimiter == "\t" else "converted.csv"
        output_file_path = os.path.join(root_dir, output_file_name)

        termbase_obj = Termbase()

        try:
            # Connect to the SDLTB (Access database) using pyodbc. [6]
            # This connection string is common for Windows, adjust DRIVER as needed for other OS/drivers.
            conn_str = f"DRIVER={{Microsoft Access Driver (*.mdb, *.accdb)}};DBQ={files}"
            db_conn = pyodbc.connect(conn_str)
            db_cursor = db_conn.cursor()

            db_cursor.execute("SELECT conceptid, text FROM mtConcepts") # [6]

            for conceptid, xml_text in db_cursor: # [19]
                entry_number = int(conceptid)
                termbase_obj.addConcept(entry_number)

                # Use lxml for robust XPath if available, otherwise fallback to ElementTree (limited XPath) [6]
                if LXET:
                    document = LXET.fromstring(xml_text)
                    def evaluate_xpath(xpath_expr, element=document):
                        result = element.xpath(xpath_expr)
                        if result:
                            return str(result) # For text content or attribute values
                        return ""
                else: # Fallback using xml.etree.ElementTree (XPath support is limited)
                    document = ET.fromstring(xml_text)
                    def evaluate_xpath(xpath_expr, element=document):
                        # This fallback is highly simplified and may not accurately translate all Java XPath expressions.
                        # It primarily handles direct element/attribute access in a rudimentary way.
                        try:
                            if xpath_expr.endswith('/@type'): # Handle attribute selection
                                parent_path = xpath_expr.rsplit('/', 1)
                                temp_element = element.find(parent_path.replace('/cG/','').replace('/','')) # Simple path cleaning
                                return temp_element.get('type') if temp_element is not None else ""
                            else: # General element text
                                temp_element = element.find(xpath_expr.replace('/cG/','').replace('/',''))
                                return temp_element.text if temp_element is not None else ""
                        except Exception:
                            return ""

                # ==================== Read entry level data ======================= [19]
                entry_creator = evaluate_xpath("/cG/trG/tr[@type='origination']")
                creation_moment_raw = evaluate_xpath("/cG/trG/tr[@type='origination']/../dt")
                entry_modifier = evaluate_xpath("/cG/trG/tr[@type='modification']")
                modification_moment_raw = evaluate_xpath("/cG/trG/tr[@type='modification']/../dt")

                # Date formatting: "YYYY-MM-DDTHH:MM:SS" -> "MM/DD/YYYY HH:MM:SS AM/PM" [20, 21]
                def format_date_from_iso_to_ampm(iso_date_str):
                    if not iso_date_str:
                        return ""
                    try:
                        dt_obj = datetime.strptime(iso_date_str, "%Y-%m-%dT%H:%M:%S")
                        return dt_obj.strftime("%m/%d/%Y %I:%M:%S %p")
                    except ValueError:
                        return iso_date_str # Return raw if parsing fails

                creation_moment = format_date_from_iso_to_ampm(creation_moment_raw)
                modification_moment = format_date_from_iso_to_ampm(modification_moment_raw)

                termbase_obj.conceptList[entry_number].setEntryCreator(entry_creator)
                termbase_obj.conceptList[entry_number].setCreationTime(creation_moment)
                termbase_obj.conceptList[entry_number].setEntryModifier(entry_modifier)
                termbase_obj.conceptList[entry_number].setModificationTime(modification_moment)

                # Process other concept-level metadata [22]
                if LXET:
                    concept_meta_nodes = document.xpath("/cG/dG/d") # Direct 'd' children of 'dG'
                    for d_element in concept_meta_nodes:
                        if 'type' in d_element.attrib:
                            meta_type = d_element.attrib['type']
                            meta_value = d_element.text or ""
                            termbase_obj.inMeta(meta_type)
                            termbase_obj.conceptList[entry_number].addMeta(meta_type, meta_value)
                else: # ElementTree fallback (more manual iteration)
                    for dG_node in document.findall("dG"):
                        for d_element in dG_node.findall("d"):
                            if 'type' in d_element.attrib:
                                meta_type = d_element.attrib['type']
                                meta_value = d_element.text or ""
                                termbase_obj.inMeta(meta_type)
                                termbase_obj.conceptList[entry_number].addMeta(meta_type, meta_value)

                # ================== Read language level data ====================== [22, 23]
                if LXET:
                    language_groups = document.xpath("/cG/lG")
                else:
                    language_groups = document.findall("lG")

                for lang_group_node in language_groups: # For each language group [23]
                    # Read language type attribute
                    if LXET:
                        lang_raw = lang_group_node.xpath("l/@type") if lang_group_node.xpath("l/@type") else ""
                    else: # ElementTree fallback
                        l_element = lang_group_node.find("l")
                        lang_raw = l_element.attrib['type'] if l_element is not None and 'type' in l_element.attrib else ""

                    lang = lang_raw.replace(" ", "_").replace("(", "").replace(")", "")
                    termbase_obj.conceptList[entry_number].addTermgroup(lang)

                    # Iterate over children of the language group (l, dG, tG) [23]
                    for element_node in (lang_group_node.xpath("./*") if LXET else list(lang_group_node)):
                        if element_node.tag == "dG": # Definition Group [23, 24]
                            for def_node in (element_node.xpath("./d") if LXET else element_node.findall("d")):
                                if 'type' in def_node.attrib:
                                    def_type = def_node.attrib['type']
                                    if def_type == "Forbidden term":
                                        term = Term(def_node.text or "")
                                        termbase_obj.conceptList[entry_number].addTerm(term, lang)
                                        term.addTermInfo("NonTerm")
                                    elif def_type == "Definition":
                                        definition = def_node.text or ""
                                        termbase_obj.conceptList[entry_number].addDef(definition, lang)
                        elif element_node.tag == "tG": # Term Group [25]
                            # Get the term word itself
                            term_word = evaluate_xpath("t", element_node) if LXET else (element_node.find("t").text if element_node.find("t") is not None else "")
                            term = Term(term_word)
                            termbase_obj.conceptList[entry_number].addTerm(term, lang)

                            # ================= Read term level data (Usage example) =================== [25]
                            for dG_node_usage in (element_node.xpath("./dG") if LXET else element_node.findall("dG")):
                                for usage_node in (dG_node_usage.xpath("./d") if LXET else dG_node_usage.findall("d")):
                                    if 'type' in usage_node.attrib and usage_node.attrib['type'] == "Usage example":
                                        term.addUsage(usage_node.text or "")

            db_cursor.close()
            db_conn.close()

            # Populate languageList (find max number of terms for any concept for each language) [26, 27]
            for concept_entry in termbase_obj.conceptList.values():
                for lang_key, termgroup_obj in concept_entry.termgroups.items():
                    if termbase_obj.inLanguageList(lang_key) < len(termgroup_obj.terms):
                        termbase_obj.setMaxNumber(lang_key, len(termgroup_obj.terms))

            # Write CSV/TXT output [27]
            with open(output_file_path, 'w', encoding='utf-8', newline='') as out: # `newline=''` is crucial for csv module
                # =================== write first line (header) ==================== [27, 28]
                header_row = []
                header_row.append("Entry_Created")
                header_row.append("Entry_Creator")
                header_row.append("Entry_LastModified")
                header_row.append("Entry_Modifier")

                for meta in termbase_obj.conceptMetaList:
                    header_row.append(meta)

                for lang_name, max_terms in termbase_obj.languageList.items():
                    header_row.append(f"{lang_name}_Def")
                    if synonyms_presentation == "Separate columns": # [28]
                        for i in range(max_terms):
                            header_row.append(lang_name)
                            header_row.append("Term_Info")
                            header_row.append("Term_Example")
                    elif synonyms_presentation == "Separated by a pipe (|)": # [28]
                        header_row.append(lang_name)
                self.write_csv_row(out, header_row, delimiter)

                # ========================== write rows (data) ======================= [29]
                for concept_entry in termbase_obj.conceptList.values():
                    row_data = []
                    row_data.append(concept_entry.getCreationTime())
                    row_data.append(concept_entry.getCreator())
                    row_data.append(concept_entry.getModificationTime())
                    row_data.append(concept_entry.getModifier())

                    for meta in termbase_obj.conceptMetaList:
                        row_data.append(concept_entry.getMeta(meta))

                    for lang_name, max_terms in termbase_obj.languageList.items():
                        termgroup = concept_entry.termgroups.get(lang_name)
                        if termgroup: # [30]
                            row_data.append(termgroup.getDefinition())

                            if synonyms_presentation == "Separate columns": # [30]
                                for stored_term in termgroup.terms:
                                    row_data.append(stored_term.getWord())
                                    row_data.append(stored_term.getTermInfo())
                                    row_data.append(stored_term.getUsage())
                                # Fill up with empty cells if fewer terms than max [31]
                                for i in range(max_terms - len(termgroup.terms)):
                                    row_data.extend(["", "", ""])
                            elif synonyms_presentation == "Separated by a pipe (|)": # [31]
                                terms_with_pipes_list = []
                                # Original Java put non-terms first with "(NOT: )", then other terms.
                                # This Python replicates that by inserting main terms at the beginning.
                                for stored_term in termgroup.terms:
                                    if stored_term.getTermInfo() == "NonTerm":
                                        terms_with_pipes_list.append(f"(NOT: {stored_term.getWord()})")
                                    else:
                                        terms_with_pipes_list.insert(0, stored_term.getWord()) # Main term first
                                row_data.append("|".join(terms_with_pipes_list))
                        else: # If no terms in given language, fill up with empty cells [32]
                            row_data.append("") # For definition
                            if synonyms_presentation == "Separate columns":
                                for i in range(max_terms):
                                    row_data.extend(["", "", ""])
                            elif synonyms_presentation == "Separated by a pipe (|)":
                                row_data.append("")

                    self.write_csv_row(out, row_data, delimiter)

            self.show_message("Conversion Complete", f"Termbase successfully converted to {output_file_name}")

        except pyodbc.Error as e: # [33, 34]
            self.show_message("Database Error (pyodbc)", f"Failed to connect to or read Access database (SDLTB): {e}\n"
                                                      "Please ensure 'Microsoft Access Driver' is installed and the SDLTB file is valid.", is_error=True)
        except (LXET.ParseError, ET.ParseError) as e: # [33]
            self.show_message("XML Parse Error", f"Failed to parse XML from SDLTB: {e}. Check SDLTB content.", is_error=True)
        except IOError as e: # [33]
            self.show_message("File Error", f"IOException: {e}", is_error=True)
        except Exception as e: # Catch any other unexpected errors [33, 34]
            self.show_message("Error", f"An unexpected error occurred during SDLTB conversion: {e}", is_error=True)

def main():
    """
    Entry point for the application.
    Checks for command-line arguments for SDLTM conversion or starts the GUI. [34-36]
    """
    if len(sys.argv) > 1:
        # Command line argument handling for SDLTM conversion
        files = []
        for arg in sys.argv[1:]:
            if arg.lower().endswith(".sdltm"):
                files.append(arg)
            else:
                print(f"Skipping '{arg}': Not an SDLTM file.")

        if files:
            # Create a dummy Tkinter root to allow file dialogs and message boxes
            # and reuse the GUI's conversion logic.
            root = tk.Tk()
            root.withdraw() # Hide the main window
            converter_cli = SDLConverter()
            converter_cli.converttm(files)
            root.destroy()
        else:
            print("Wrong file type or no SDLTM files provided in arguments.")
        sys.exit()
    else:
        # Start GUI application [35]
        app = SDLConverter()
        app.mainloop()

if __name__ == "__main__":
    main()