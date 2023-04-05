from typing import List, Optional, Tuple
from bs4 import BeautifulSoup
import gradio as gr
from modules import script_callbacks, scripts, hashes
from modules.sd_models import CheckpointInfo, checkpoint_tiles, checkpoint_alisases, list_models
from modules.sd_hijack import model_hijack
from modules.ui import create_refresh_button, save_style_symbol
from modules.shared import opts, OptionInfo, hypernetworks, reload_hypernetworks
from modules.ui_components import FormRow, ToolButton
import sqlite3
from sqlite3 import Error
from pathlib import Path
import requests
from requests.models import Response
from bs4 import BeautifulSoup
from enum import Enum
from modules.paths_internal import extensions_builtin_dir
from starlette.responses import JSONResponse
import sys

# Build-in extensions are loaded after extensions so we need to add it manually
sys.path.append(str(Path(extensions_builtin_dir, "Lora")))
import lora
# Remove from path again so we don't affect other modules
sys.path.remove(str(Path(extensions_builtin_dir, "Lora")))

notes_symbol = '\U0001F4DD' # 📝
conn = None
reload_hypernetworks() # No hypernetworks are loaded yet so we have to load the manually

class ModelType(Enum):
    Checkpoint = 1
    Hypernetwork = 2
    LoRA = 3
    Textual_Inversion = 4

def create_connection(db_file: str) -> None:
    """ 
    Creates a database connection to a SQLite database.
    
    :param db_file: The file path of the database file.
    :return: None.
    """
    global conn
    try:
        conn = sqlite3.connect(db_file, check_same_thread=False)
    except Error as e:
        print(e)

def execute_sql(sql: str, *data) -> list:
    """
    Executes an SQL statement and returns the result as a list of rows.

    :param sql: The SQL statement.
    :param data: Any data to be passed to the SQL statement.
    :return: A list of rows.
    """
    try:
        cur = conn.cursor()
        cur.execute(sql, data)
        conn.commit()
        return cur.fetchall()
    except Error as e:
        print("Query:", sql)
        print("Data:", data)
        print("Error:", e)

def setup_db() -> None:
    """
    Creates all tables we need if they do not already exist.
    
    :return: None.
    """
    meta_table = """
    CREATE TABLE IF NOT EXISTS meta (
        version text PRIMARY KEY
    );
    """
    notes_table = """
    CREATE TABLE IF NOT EXISTS notes (
        model_hash text PRIMARY KEY,
        note text NOT NULL,
        model_type text NOT NULL
    );
    """
    execute_sql(meta_table)
    execute_sql(notes_table)
    upgrade_db()

def upgrade_db() -> None:
    """
    Checks the version and upgrades the database from a previous version if needed
    
    :return: None.
    """
    get_version = """
    SELECT MAX(version) FROM meta;
    """
    set_version = """
    REPLACE INTO meta(version) VALUES(?);
    """
    rows = execute_sql(get_version)
    version = rows[0][0] if rows != [] else "1"
    if version == "1":
        upgrade_note_table = f"""
        ALTER TABLE notes ADD COLUMN model_type text NOT NULL DEFAULT '{ModelType.Checkpoint.value}';
        """
        execute_sql(upgrade_note_table)
        execute_sql(set_version, 2)

def set_note(model_type : ModelType, model_hash: str, note: str) -> None:
    """
    Save a note in the database for the given model.
    
    :param model_type: The type of the model.
    :param model_hash: The full sha256 hash of the model.
    :param note: The note that should be saved.
    :return: None.
    """
    sql = """
    REPLACE INTO notes(model_hash, note, model_type) VALUES(?, ?, ?);
    """
    execute_sql(sql, model_hash, note, model_type.value)

def get_note(model_hash: str) -> str:
    """
    Retrieve the saved note for the given model.
    
    :param model_hash: The full sha256 hash of the model.
    :return: The saved note for the saved model or an empty string.
    """
    sql = """
    SELECT note FROM notes WHERE model_hash = ?
    """
    rows = execute_sql(sql, model_hash)
    note : str = rows[0][0] if rows != [] else ""
    return note

# Helper function to calculate Levenshtein distance between two strings
def levenshtein_distance(s1: str, s2: str) -> int:
    """
    Calculates the Levenshtein distance between two strings.

    :param s1: The first string to compare.
    :param s2: The second string to compare.
    :return: An integer representing the number of edits required to transform s1 into s2.
    """
    if len(s1) > len(s2):
        s1, s2 = s2, s1
    distances = range(len(s1) + 1)
    for i2, c2 in enumerate(s2):
        distances_ = [i2+1]
        for i1, c1 in enumerate(s1):
            if c1 == c2:
                distances_.append(distances[i1])
            else:
                distances_.append(1 + min((distances[i1], distances[i1 + 1], distances_[-1])))
        distances = distances_
    return distances[-1]

def match_model_type(string) -> ModelType:
    """
    Matches a string to a ModelType by finding the closest match based on Levenshtein distance.

    :param string: The string to match.
    :return: A ModelType representing the closest match to the input string.
    """
    # Convert input string to lowercase and remove spaces
    string = string.lower().replace(" ", "_")

    # Find the closest match to the input string
    closest_match = None
    closest_distance = float("inf")
    for member in ModelType:
        distance = levenshtein_distance(string, member.name.lower())
        if distance < closest_distance:
            closest_distance = distance
            closest_match = member

    # Return the closest match
    return closest_match

def api_get_note_by_hash(hash : str) -> JSONResponse:
    """
    Get the note from the given model.
    
    :param hash: The sha256 hash of the model.
    :return: JSONResponse containing the "note".
    """
    return JSONResponse({"note": get_note(hash)})

def api_get_note_by_name(type : str, name : str) -> JSONResponse:
    """
    Get the note from the given model.
    
    :param type: The type of the model. Any format of string is accepted and will be converted to the correct format.
    :param name: The name of the model.
    :return: JSONResponse containing the "note".
    """
    real_model_type = match_model_type(type)
    sha256 = get_model_sha256(real_model_type, name)
    return JSONResponse({"note": get_note(sha256)})

def api_set_note_by_hash(type : str, hash : str, note : str) -> JSONResponse:
    """
    Sets the note for the given model.
    
    :param type: The type of the model. Any format of string is accepted and will be converted to the correct format.
    :param hash: The sha256 hash of the model.
    :param note: The note that should be saved.
    :return: JSONResponse containing the "note".
    """
    real_model_type = match_model_type(type)
    set_note(model_hash=hash, note=note, model_type=real_model_type)
    return JSONResponse({"success": True})

def api_set_note_by_name(type : str, name : str, note : str) -> JSONResponse:
    """
    Sets the note for the given model.
    
    :param type: The type of the model. Any format of string is accepted and will be converted to the correct format.
    :param name: The name of the model.
    :param note: The note that should be saved.
    :return: JSONResponse containing the "note".
    """
    real_model_type = match_model_type(type)
    sha256 = get_model_sha256(real_model_type, name)
    set_note(model_hash=sha256, note=note, model_type=real_model_type)
    return JSONResponse({"success": True})

def add_api_endpoints(fastapi) -> None:
    """
    Adds all API endpoints
    
    :param fastapi: Instance of fastapi.
    :return: None.
    """
    fastapi.add_api_route("/model_notes/get_note_by_hash", api_get_note_by_hash, methods=["GET"])
    fastapi.add_api_route("/model_notes/get_note_by_name", api_get_note_by_name, methods=["GET"])
    fastapi.add_api_route("/model_notes/set_note_by_hash", api_set_note_by_hash, methods=["POST"])
    fastapi.add_api_route("/model_notes/set_note_by_name", api_set_note_by_name, methods=["POST"])

def on_app_started(gradio, fastapi) -> None:
    """
    Called when the application starts.
    
    :param gradio: Instance of gradio.
    :param fastapi: Instance of fastapi.
    :return: None.
    """
    create_connection(Path(Path(__file__).parent.parent.resolve(), "notes.db"))
    setup_db()
    add_api_endpoints(fastapi)

def get_model_sha256(model_type : ModelType, model_name : str) -> str:
    """
    Returns the sha256 of the given model.

    :param model_type: The type of model.
    :param model_name: The name of the model.
    :return: The sha256 of the model.
    """
    if model_type == ModelType.Checkpoint:
        checkpoint_info : Optional[CheckpointInfo] = checkpoint_alisases.get(model_name)
        if checkpoint_info is None:
            return
        sha256 = checkpoint_info.sha256
    elif model_type == ModelType.Hypernetwork:
        hypernetwork_path = hypernetworks.get(model_name)
        sha256 = hashes.sha256(hypernetwork_path, f'hypernet/{model_name}')
    elif model_type == ModelType.LoRA:
        lora_on_disk = lora.available_loras[model_name]
        sha256 = hashes.sha256(lora_on_disk.filename, f'lora/{lora_on_disk.name}')
    elif model_type == ModelType.Textual_Inversion:
        embedding = model_hijack.embedding_db.word_embeddings[model_name]
        sha256 = hashes.sha256(embedding.filename, f'textual_inversion/{embedding.name}')
    return str(sha256)

def on_model_selection(model_type : ModelType, model_name : str) -> str:
    """
    Get the note associated with the selected model.
    
    :param model_type: The type of the model.
    :param model_name: The name of the model.
    :return: The note associated with the model.
    """
    result = get_note(get_model_sha256(model_type, model_name))
    return gr.update(value=result, interactive=True)

def on_save_note(model_type : ModelType, model_name : str, note : str) -> None:
    """
    Save a note for the selected model.
    
    :param model_type: The type of the model.
    :param model_name: The name of the model.
    :param note: The note that should be saved.
    :return: The note associated with the model.
    """
    set_note(model_hash=get_model_sha256(model_type, model_name), note=note, model_type=model_type)

def on_civitai(model_type : ModelType, model_name : str, model_note : str) -> str:
    """
    Gets the model description from Civitai and updates the model note.

    :param model_type: The type of the model.
    :param model_name: The name of the model.
    :param model_note: The current model note.
    :return: The updated model note. The given model note if the model is not selected or the model description could not be retrieved.
    """
    model_version_info : Response = requests.get(f"https://civitai.com/api/v1/model-versions/by-hash/{get_model_sha256(model_type, model_name)}")
    if model_version_info.status_code == 200:
        model_version_info_json : dict = model_version_info.json()
        civitai_model_id : str = model_version_info_json.get("modelId")
        model_info : Response = requests.get(f"https://civitai.com/api/v1/models/{civitai_model_id}")
        if model_info.status_code == 200:
            model_info_json : dict = model_info.json()
            formatted_model_description : str = f'Model Description:\n{model_info_json.get("description")}\n\nVersion Description:\n{model_version_info_json.get("description")}\n\nTrigger Words:\n{model_version_info_json.get("trainedWords")}'
            soup = BeautifulSoup(formatted_model_description, 'html.parser')
            formatted_model_description = soup.get_text("\n", strip=True)
            return gr.update(value=formatted_model_description)
    return gr.update(value=model_note, interactive=True)

def get_textual_inversion_embeddings() -> List[str]:
    embeddings = []
    for embedding in model_hijack.embedding_db.word_embeddings.values():
        embeddings.append(embedding.name)
    embeddings.sort()
    return embeddings

def get_hypernetworks() -> List[str]:
    hypernetworks_names = list(hypernetworks.keys())
    hypernetworks_names.sort()
    return hypernetworks_names

def get_loras() -> List[str]:
    loras = []
    for name in lora.available_loras.keys():
        loras.append(name)
    return loras

def on_ui_tabs() -> Tuple[gr.Blocks, str, str]:
    """
    Create the UI tab for model notes.
    
    :return: A tuple containing the UI tab for model notes.
    """
    suported_models = ["Textual Inversion", "Hypernetworks", "Checkpoints", "LoRA"]
    with gr.Blocks(analytics_enabled=False) as main_tab:
        for model in suported_models:
            with gr.Tab(model):
                with FormRow(elem_id="notes_mode_selection"):
                    with FormRow(variant='panel'):
                        if model == "Textual Inversion":
                            notes_model_select = gr.Dropdown(get_textual_inversion_embeddings(), elem_id="notes_embedding_model_dropdown", label="Select Textual Inversion", interactive=True)
                            create_refresh_button(notes_model_select, lambda: model_hijack.embedding_db.load_textual_inversion_embeddings(force_reload=True), lambda: {"choices": get_textual_inversion_embeddings()}, "refresh_notes_embedding_model_dropdown")
                        elif model == "Hypernetworks":
                            notes_model_select = gr.Dropdown(get_hypernetworks(), elem_id="notes__hypernetwork_model_dropdown", label="Select Hypernetwork", interactive=True)
                            create_refresh_button(notes_model_select, reload_hypernetworks, lambda: {"choices": get_hypernetworks()}, "refresh_notes_hypernetwork_model_dropdown")
                        elif model == "LoRA":
                            notes_model_select = gr.Dropdown(get_loras(), elem_id="notes_lora_model_dropdown", label="Select LoRA", interactive=True)
                            create_refresh_button(notes_model_select, lora.list_available_loras, lambda: {"choices": get_loras()}, "refresh_notes_lora_model_dropdown")
                        elif model == "Checkpoints":
                            notes_model_select = gr.Dropdown(checkpoint_tiles(), elem_id="notes_lora_model_dropdown", label="Select Checkpoint", interactive=True)
                            create_refresh_button(notes_model_select, list_models, lambda: {"choices": checkpoint_tiles()}, "refresh_notes_lora_model_dropdown")
                    if not opts.model_note_autosave:
                        save_button = gr.Button(value="Save changes " + save_style_symbol, variant="primary", elem_id="save_model_note")
                    civitai_button = gr.Button(value="Get description from Civitai", variant="secondary", elem_id="notes_civitai_button")
                note_box = gr.Textbox(label="Note", lines=25, elem_id="model_notes_textbox", placeholder="Make a note about the model selected above!", interactive=False)
                if model == "Textual Inversion":
                    notes_model_select.change(fn=lambda select: on_model_selection(ModelType.Textual_Inversion, select), inputs=[notes_model_select], outputs=[note_box])
                    if opts.model_note_autosave:
                        note_box.change(fn=lambda select, note: on_save_note(ModelType.Textual_Inversion, select, note), inputs=[notes_model_select, note_box], outputs=[])
                    else:
                        save_button.click(fn=lambda select, note: on_save_note(ModelType.Textual_Inversion, select, note), inputs=[notes_model_select, note_box], outputs=[])
                    civitai_button.click(fn=lambda select, note: on_civitai(ModelType.Textual_Inversion, select, note), inputs=[notes_model_select, note_box], outputs=[note_box])
                elif model == "Hypernetworks":
                    notes_model_select.change(fn=lambda select: on_model_selection(ModelType.Hypernetwork, select), inputs=[notes_model_select], outputs=[note_box])
                    if opts.model_note_autosave:
                        note_box.change(fn=lambda select, note: on_save_note(ModelType.Hypernetwork, select, note), inputs=[notes_model_select, note_box], outputs=[])
                    else:
                        save_button.click(fn=lambda select, note: on_save_note(ModelType.Hypernetwork, select, note), inputs=[notes_model_select, note_box], outputs=[])
                    civitai_button.click(fn=lambda select, note: on_civitai(ModelType.Hypernetwork, select, note), inputs=[notes_model_select, note_box], outputs=[note_box])
                elif model == "LoRA":
                    notes_model_select.change(fn=lambda select: on_model_selection(ModelType.LoRA, select), inputs=[notes_model_select], outputs=[note_box])
                    if opts.model_note_autosave:
                        note_box.change(fn=lambda select, note: on_save_note(ModelType.LoRA, select, note), inputs=[notes_model_select, note_box], outputs=[])
                    else:
                        save_button.click(fn=lambda select, note: on_save_note(ModelType.LoRA, select, note), inputs=[notes_model_select, note_box], outputs=[])
                    civitai_button.click(fn=lambda select, note: on_civitai(ModelType.LoRA, select, note), inputs=[notes_model_select, note_box], outputs=[note_box])
                elif model == "Checkpoints":
                    notes_model_select.change(fn=lambda select: on_model_selection(ModelType.Checkpoint, select), inputs=[notes_model_select], outputs=[note_box])
                    if opts.model_note_autosave:
                        note_box.change(fn=lambda select, note: on_save_note(ModelType.Checkpoint, select, note), inputs=[notes_model_select, note_box], outputs=[])
                    else:
                        save_button.click(fn=lambda select, note: on_save_note(ModelType.Checkpoint, select, note), inputs=[notes_model_select, note_box], outputs=[])
                    civitai_button.click(fn=lambda select, note: on_civitai(ModelType.Checkpoint, select, note), inputs=[notes_model_select, note_box], outputs=[note_box])
    return (main_tab, "Model Notes", "model_notes"),

def on_ui_settings() -> None:
    """
    Add our options to the UI settings page.

    :return: None
    """
    opts.add_option("model_note_autosave", OptionInfo(default=False, label="Enable autosaving edits in note fields", component=gr.Checkbox, section=("model-notes", "Model-Notes")))

def on_script_unloaded() -> None:
    """
    Close the database connection when the script is unloaded.

    :return: None
    """
    if conn:
        conn.close()

script_callbacks.on_ui_tabs(on_ui_tabs)
script_callbacks.on_ui_settings(on_ui_settings)
script_callbacks.on_script_unloaded(on_script_unloaded)
script_callbacks.on_app_started(on_app_started)

def toggle_visibility(is_visible: bool) -> Tuple[bool, gr.update]:
    """
    Toggle the visibility of an object in the UI.
    
    :param is_visible: The current visibility of the object.
    :return: The inverted visibility and a gradio update with the visibility set.
    """
    is_visible = not is_visible
    return is_visible, gr.update(visible=is_visible)

class NoteButtons(scripts.Script):
    """This script creates a button for users to add notes about a selected model."""

    note_container = gr.Column(min_width=1920, elem_id="notes_container", visible=False)
    state_visible = gr.State(value=False)

    def title(self) -> str:
        """
        Return the title of the script.

        :return: The title of the script.
        """
        return "Model Notes"

    def show(self, is_img2img: bool) -> object:
        """
        Return the show condition of the script.
        
        :param is_img2img: If the current tab is img2img .
        :return: Object that represents that the script should be shown at all times.
        """
        return scripts.AlwaysVisible

    def on_save_note(self, note: str) -> None:
        """
        Save a note about the selected model.
        
        :param note: The note that should be saved for the selected model.
        :return: None
        """
        set_note(model_hash=opts.sd_checkpoint_hash, note=note, model_type=ModelType.Checkpoint)

    def on_get_note(self) -> gr.update:
        """
        Get the note about the selected model and update it to the UI.
        
        :return: Gradio update setting the value to the note content and the lable to the models name.
        """
        return gr.update(value=get_note(opts.sd_checkpoint_hash), label=f"Note on {opts.sd_model_checkpoint}")

    def after_component(self, component, **kwargs):
        """
        Create the UI for adding a note and updating it.

        This function creates a button, a textbox, and two buttons for users to save or update the note.

        :param component: The component that was added toy the UI.
        :param kwargs: Additional arguments about the component.
        :return: None
        """

        if kwargs.get("elem_id") and "_style_create" in kwargs.get("elem_id"):

            notes_tool_btn = ToolButton(value=notes_symbol, elem_id="model_notes_tool")

            def toggle_visibility(is_visible: bool) -> Tuple[bool, gr.update]:
                """
                Toggles the visibility of an element.

                :param is_visible: A boolean representing the current visibility of the element.
                :return: A tuple with the updated visibility and gr.update.
                """
                is_visible = not is_visible
                return is_visible, gr.update(visible=is_visible)

            state_visible = gr.State(value=False)
            notes_tool_btn.click(fn=toggle_visibility, inputs=[state_visible], outputs=[state_visible, self.note_container])

        if kwargs.get("elem_id") and "_neg_prompt" in kwargs.get("elem_id"):
            with gr.Column(min_width=1920, elem_id="notes_container", visible=False) as self.note_container:  # Pushes our stuff onto a new row at 1080p screen resolution
                with FormRow(elem_id="notes_mode_selection"):
                    tex = gr.Textbox(label="Note", lines=5, elem_id="model_notes_textbox", placeholder="Make a note about the model selected above!", interactive=True)
                if opts.model_note_autosave:
                    tex.change(fn=self.on_save_note, inputs=[tex], outputs=[])
                else:
                    save_button = gr.Button(value="Save changes " + save_style_symbol, variant="primary", elem_id="save_model_note")
                    save_button.click(fn=self.on_save_note, inputs=[tex], outputs=[])
                update_button = ToolButton(value=notes_symbol, elem_id="model_note_update", visible=False)
                update_button.click(fn=self.on_get_note, inputs=[], outputs=[tex])