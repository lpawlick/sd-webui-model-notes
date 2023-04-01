from typing import Optional, Tuple
from bs4 import BeautifulSoup
import gradio as gr
from modules import script_callbacks, scripts
from modules.sd_models import CheckpointInfo, checkpoint_tiles, checkpoint_alisases, list_models
from modules.ui import create_refresh_button, save_style_symbol
from modules.shared import opts, OptionInfo
from modules.ui_components import FormRow, ToolButton
import sqlite3
from sqlite3 import Error
from pathlib import Path
import requests
from requests.models import Response
from bs4 import BeautifulSoup

notes_symbol = '\U0001F4DD' # 📝
conn = None

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
    notes_table = """
    CREATE TABLE IF NOT EXISTS notes (
        model_hash text PRIMARY KEY,
        note text NOT NULL
    );
    """
    execute_sql(notes_table)


def set_note(model_hash: str, note: str) -> None:
    """
    Save a note in the database for the given model.
    
    :param model_hash: The full sha256 hash of the model.
    :param note: The note that should be saved.
    :return: None.
    """
    sql = """
    REPLACE INTO notes(model_hash, note) VALUES(?, ?);
    """
    execute_sql(sql, model_hash, note)

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

def on_app_started(gradio, fastapi) -> None:
    """
    Called when the application starts.
    
    :param gradio: Instance of gradio.
    :param fastapi: Instance of fastapi.
    :return: None.
    """
    create_connection(Path(Path(__file__).parent.parent.resolve(), "notes.db"))
    setup_db()

def on_model_selection(model_name : str) -> str:
    """
    Get the note associated with the selected model.
    
    :param model_name: The name of the model.
    :return: The note associated with the model.
    """
    checkpoint_info : CheckpointInfo = checkpoint_alisases.get(model_name)
    if checkpoint_info.sha256 is None: # Calculate hash if not already exists
        checkpoint_info.calculate_shorthash()
    result = get_note(str(checkpoint_info.sha256))
    return gr.update(value=result, interactive=True)

def on_save_note(model_name : str, note : str) -> None:
    """
    Save a note for the selected model.
    
    :param model_name: The name of the model.
    :param note: The note that should be saved.
    :return: The note associated with the model.
    """
    checkpoint_info : Optional[CheckpointInfo] = checkpoint_alisases.get(model_name)
    if checkpoint_info is None:
        return
    set_note(checkpoint_info.sha256, note)

def on_civitai(model_name : str, model_note : str) -> str:
    """
    Gets the model description from Civitai and updates the model note.

    :param model_name: The name of the model.
    :param model_note: The current model note.
    :return: The updated model note. The given model note if the model is not selected or the model description could not be retrieved.
    """
    checkpoint_info : Optional[CheckpointInfo] = checkpoint_alisases.get(model_name)
    if checkpoint_info is None: # No model is selected
        return
    model_version_info : Response = requests.get(f"https://civitai.com/api/v1/model-versions/by-hash/{checkpoint_info.sha256}")
    if model_version_info.status_code == 200:
        model_version_info_json : dict = model_version_info.json()
        civitai_model_id : str = model_version_info_json.get("modelId")
        model_info : Response = requests.get(f"https://civitai.com/api/v1/models/{civitai_model_id}")
        if model_info.status_code == 200:
            model_info_json : dict = model_info.json()
            formatted_model_description : str = f'Model Description:\n{model_info_json.get("description")}\n\nVersion Description:\n{model_version_info_json.get("description")}\n\nTrigger Words:\n{model_version_info_json.get("trainedWords")}'
            soup = BeautifulSoup(formatted_model_description, 'html.parser')
            formatted_model_description = soup.get_text("\n", strip=True)
            on_save_note(model_name, formatted_model_description)
            return gr.update(value=formatted_model_description)
    return gr.update(value=model_note, interactive=True)

def on_ui_tabs() -> Tuple[gr.Blocks, str, str]:
    """
    Create the UI tab for model notes.
    
    :return: A tuple containing the UI tab for model notes.
    """
    with gr.Blocks(analytics_enabled=False) as tab:
        with FormRow(elem_id="notes_mode_selection"):
            with FormRow(variant='panel'):
                notes_model_select = gr.Dropdown(checkpoint_tiles(), elem_id="notes_model_dropdown", label="Select Stable Diffusion Checkpoint", interactive=True)
                create_refresh_button(notes_model_select, list_models, lambda: {"choices": checkpoint_tiles()}, "refresh_notes_model_dropdown")
            if not opts.model_note_autosave:
                save_button = gr.Button(value="Save changes " + save_style_symbol, variant="primary", elem_id="save_model_note")
            civitai_button = gr.Button(value="Get description from Civitai", variant="secondary", elem_id="notes_civitai_button")
        note_box = gr.Textbox(label="Note", lines=25, elem_id="model_notes_textbox", placeholder="Make a note about the model selected above!", interactive=False)
        if opts.model_note_autosave:
            note_box.change(fn=on_save_note, inputs=[notes_model_select, note_box], outputs=[])
        notes_model_select.change(fn=on_model_selection, inputs=[notes_model_select], outputs=[note_box])
        civitai_button.click(fn=on_civitai, inputs=[notes_model_select, note_box], outputs=[note_box])
        if not opts.model_note_autosave:
            save_button.click(fn=on_save_note, inputs=[notes_model_select, note_box], outputs=[])
    return (tab, "Model Notes", "model_notes"),

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
        set_note(opts.sd_checkpoint_hash, note)

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