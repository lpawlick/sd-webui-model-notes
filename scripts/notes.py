from typing import List, Optional, Tuple, Union
from bs4 import BeautifulSoup
import gradio as gr
from gradio import utils
import inspect
from modules import script_callbacks, scripts, hashes
from modules.sd_models import CheckpointInfo, checkpoint_tiles, checkpoint_alisases, list_models
from modules.sd_hijack import model_hijack
from modules.ui import create_refresh_button, save_style_symbol
from modules import shared, sd_models
from modules.ui_components import FormRow, ToolButton
from modules import ui_extra_networks
from modules.ui_extra_networks_textual_inversion import ExtraNetworksPageTextualInversion
from modules.ui_extra_networks_checkpoints import ExtraNetworksPageCheckpoints
from modules.ui_extra_networks_hypernets import ExtraNetworksPageHypernetworks
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
import threading
import time
import html2markdown
import csv
import os

# Build-in extensions are loaded after extensions so we need to add it manually
sys.path.append(str(Path(extensions_builtin_dir, "Lora")))
import lora
from ui_extra_networks_lora import ExtraNetworksPageLora
# Remove from path again so we don't affect other modules
sys.path.remove(str(Path(extensions_builtin_dir, "Lora")))

notes_symbol = '\U0001F4DD' # 📝
conn = None
conn_lock = threading.Lock()
shared.reload_hypernetworks() # No hypernetworks are loaded yet so we have to load the manually
md_renderer = utils.get_markdown_parser()

class ModelType(Enum):
    """
    Enumeration of various types of models.
    """
    Checkpoint = 1
    Hypernetwork = 2
    LoRA = 3
    Textual_Inversion = 4

class ResultType(Enum):
    """
    Enumeration of possible result types after processing.
    """
    success = 1
    not_found = 2
    error = 3
    skipped = 4

class FileTypes(Enum):
    """
    Enumeration of supported file types along with their extensions, descriptions, and IDs.
    
    :param extension: The file extension.
    :param description: The file type description.
    :param id: The unique identifier for the file type.
    """

    Plain_text = ("txt", "Plaint text (*.txt)", 0)
    CSV = ("csv", "Comma-Separated (*.csv)", 1)
    Markdown = ("md", "Markdown (*.md)", 2)
    HTML = ("html", "HTML (*.html)", 3)
    
    def __init__(self, extension, description, id):
        self.extension = extension
        self.description = description
        self.id = id
        
    def __str__(self):
        return self.description
    
    @classmethod
    def from_extension(cls, extension_str):
        for filetype in cls:
            if filetype.extension == extension_str:
                return filetype
        raise ValueError(f"Unknown extension: {extension_str}")
        
    @classmethod
    def from_description(cls, description_str):
        for filetype in cls:
            if str(filetype) == description_str:
                return filetype
        raise ValueError(f"Unknown description: {description_str}")

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
        with conn_lock:
            with conn:
                cur = conn.cursor()
                cur.execute(sql, data)
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

def match_enum(string, enum_type):
    """
    Matches a string to the given Enum by finding the closest match based on Levenshtein distance.

    :param string: The string to match.
    :return: A Enum value representing the closest match to the input string.
    """
    # Convert input string to lowercase and remove spaces
    string = string.lower().replace(" ", "_")

    # Find the closest match to the input string
    closest_match = None
    closest_distance = float("inf")
    for member in enum_type:
        distance = levenshtein_distance(string, member.name.lower())
        if distance < closest_distance:
            closest_distance = distance
            closest_match = member

    # Return the closest match
    return closest_match

def convert_markdown_to_html(markdown: str) -> str:
    """
    Converts markdown to HTML.

    :param markdown: The markdown to convert.
    :return: The converted HTML.
    """
    markdown = inspect.cleandoc(markdown)
    markdown = md_renderer.render(markdown)
    return markdown

def api_get_note_by_hash(hash : str, markdown : bool = False) -> JSONResponse:
    """
    Get the note from the given model.
    
    :param hash: The sha256 hash of the model.
    :return: JSONResponse containing the "note".
    """
    note = get_note(hash)
    return JSONResponse({"note": convert_markdown_to_html(note) if markdown else note})

def api_get_note_by_name(type : str, name : str, markdown : bool = False) -> JSONResponse:
    """
    Get the note from the given model.
    
    :param type: The type of the model. Any format of string is accepted and will be converted to the correct format.
    :param name: The name of the model.
    :return: JSONResponse containing the "note".
    """
    real_model_type = match_enum(type, ModelType)
    sha256 = get_model_sha256(real_model_type, name)
    note = get_note(sha256)
    return JSONResponse({"note": convert_markdown_to_html(note) if markdown else note})

def api_set_note_by_hash(type : str, hash : str, note : str) -> JSONResponse:
    """
    Sets the note for the given model.
    
    :param type: The type of the model. Any format of string is accepted and will be converted to the correct format.
    :param hash: The sha256 hash of the model.
    :param note: The note that should be saved.
    :return: JSONResponse containing the "note".
    """
    real_model_type = match_enum(type, ModelType)
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
    real_model_type = match_enum(type, ModelType)
    sha256 = get_model_sha256(real_model_type, name)
    set_note(model_hash=sha256, note=note, model_type=real_model_type)
    return JSONResponse({"success": True})

def api_convert_text_to_html(text : str) -> JSONResponse:
    """
    Converts the given text to HTML.
    
    :param text: The text that should be converted.
    :return: JSONResponse containing the "html".
    """
    html = convert_markdown_to_html(text)
    return JSONResponse({"html": html})

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
    fastapi.add_api_route("/model_notes/utils/convert_markdown_to_html", api_convert_text_to_html, methods=["GET"])

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
    overwrite_load_descriptions()

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
        hypernetwork_path = shared.hypernetworks.get(model_name)
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
    return gr.update(value=result, interactive=True, lines=result.count("\n") + 1)

def on_save_note(model_type : ModelType, model_name : str, note : str) -> None:
    """
    Save a note for the selected model.
    
    :param model_type: The type of the model.
    :param model_name: The name of the model.
    :param note: The note that should be saved.
    :return: The note associated with the model.
    """
    set_note(model_hash=get_model_sha256(model_type, model_name), note=note, model_type=model_type)

def download_description_from_civit(model_type : ModelType, model_name : str, download_markdown: bool) -> str:
    """
    Downloads the model description from Civitai.

    :param model_type: The type of the model.
    :param model_name: The name of the model.
    :param download_markdown: Whether to convert the description in into the markdown format
    :return: The formatted model description.
    """
    model_version_info : Response = requests.get(f"https://civitai.com/api/v1/model-versions/by-hash/{get_model_sha256(model_type, model_name)}")
    if model_version_info.status_code == 200:
        model_version_info_json : dict = model_version_info.json()
        civitai_model_id : str = model_version_info_json.get("modelId")
        model_info : Response = requests.get(f"https://civitai.com/api/v1/models/{civitai_model_id}")
        if model_info.status_code == 200:
            model_info_json : dict = model_info.json()
            formatted_model_description : str = f'Model Description:\n{model_info_json.get("description")}\n\nVersion Description:\n{model_version_info_json.get("description")}\n\nTrigger Words:\n{", ".join(model_version_info_json.get("trainedWords"))}'
            if download_markdown:
                formatted_model_description = html2markdown.convert(formatted_model_description)
            else:
                soup = BeautifulSoup(formatted_model_description, 'html.parser')
                formatted_model_description = soup.get_text("\n", strip=True)
            return formatted_model_description
        elif model_info.status_code == 429:
            time.sleep(int(model_info.headers["Retry-After"]))
            return download_description_from_civit(model_type, model_name, download_markdown)
    elif model_version_info.status_code == 429:
        time.sleep(int(model_version_info.headers["Retry-After"]))
        return download_description_from_civit(model_type, model_name, download_markdown)
    return ""

def download_image_from_civitai(model_type : ModelType, model_name : str, local_path: str) -> bool:
    """
    Downloads and saves a preview image from civitai.

    :param model_type: The type of the model.
    :param model_name: The name of the model.
    :param local_path: The path where the image should be saved.
    :return: Whether the image was successfully downloaded.
    """
    model_version_info : Response = requests.get(f"https://civitai.com/api/v1/model-versions/by-hash/{get_model_sha256(model_type, model_name)}")
    if model_version_info.status_code == 200:
        model_version_info_json : dict = model_version_info.json()
        civitai_preview_images : List[dict] = model_version_info_json.get("images")
        if len(civitai_preview_images) > 0:
            image_url = civitai_preview_images[0].get("url")
            image_data = requests.get(image_url, stream=True)
            if image_data.status_code == 200:
                with open(local_path, 'wb') as file:
                    for chunk in image_data.iter_content(chunk_size=8192):
                        file.write(chunk)
                return True
            elif image_data.status_code == 429:
                time.sleep(int(image_data.headers["Retry-After"]))
                return download_image_from_civitai(model_type, model_name)
    elif model_version_info.status_code == 429:
        time.sleep(int(model_version_info.headers["Retry-After"]))
        return download_image_from_civitai(model_type, model_name)
    return False

def on_civitai(model_type : ModelType, model_name : str, model_note : str) -> str:
    """
    Gets the model description from Civitai and updates the model note.

    :param model_type: The type of the model.
    :param model_name: The name of the model.
    :param model_note: The current model note.
    :return: The updated model note. The given model note if the model is not selected or the model description could not be retrieved.
    """
    description = download_description_from_civit(model_type=model_type, model_name=model_name, download_markdown=shared.opts.model_note_markdown)
    if description != "":
        return gr.update(value=description)
    else:
        return gr.update(value=model_note, interactive=True)

def on_get_all_civitai(model_types, overwrite : bool, dl_markdown : bool, dl_preview_image : bool, dl_preview_image_overwrite : bool, pr=gr.Progress()):
    """
    Gets the model descriptions for all selected models from civitai

    :param model_types: The selected model types.
    :param overwrite: Whether to overwrite existing notes.
    :param dl_markdown: Whether to convert the description in into the markdown format
    :param dl_preview_image: Whether to download the preview image
    :param dl_preview_image_overwrite: Whether to overwrite existing preview images
    :param pr: The progress bar. Do not set this manually.
    :return: A string containing information about the download
    """
    
    if model_types == []:
        return "No models selected, nothing to download."

    if not shared.opts.model_note_markdown:
        dl_markdown = False

    stats = {model: {"success": 0, "failed": 0, "skipped": 0, "img_success": 0, "img_failed": 0, "img_skipped": 0} for model in model_types}

    if "Textual Inversion" in model_types:
        textual_inversions = get_textual_inversion_embeddings()
        if dl_preview_image:
            extra_page = ExtraNetworksPageTextualInversion()
        for embedding in pr.tqdm(textual_inversions, desc="Downloading Textual Inversion Descriptions", total=len(textual_inversions), unit="embeddings"):
            if dl_preview_image:
                path, ext = os.path.splitext(model_hijack.embedding_db.word_embeddings.get(embedding).filename)
                preview_path = extra_page.find_preview(path)
                if preview_path is None or dl_preview_image_overwrite:
                    if download_image_from_civitai(ModelType.Textual_Inversion, embedding, f"{path}.preview.{shared.opts.samples_format}"):
                        stats["Textual Inversion"]["img_success"] += 1
                    else:
                        stats["Textual Inversion"]["img_failed"] += 1
                else:
                    stats["Textual Inversion"]["img_skipped"] += 1
            
            description = download_description_from_civit(ModelType.Textual_Inversion, embedding, dl_markdown)
            if not overwrite:
                note = get_note(model_hash=get_model_sha256(ModelType.Textual_Inversion, embedding))
                if note != "":
                    stats["Textual Inversion"]["skipped"] += 1
                    continue
            if description != "":
                set_note(model_hash=get_model_sha256(ModelType.Textual_Inversion, embedding), note=description, model_type=ModelType.Textual_Inversion)
                stats["Textual Inversion"]["success"] += 1
            else:
                stats["Textual Inversion"]["failed"] += 1

    if "Hypernetworks" in model_types:
        hypernetworks = get_hypernetworks()
        if dl_preview_image:
            extra_page = ExtraNetworksPageHypernetworks()
        for hypernetwork in pr.tqdm(hypernetworks, desc="Downloading Hypernetwork Descriptions", total=len(hypernetworks), unit="hypernetworks"):
            if dl_preview_image:
                path, ext = os.path.splitext(shared.hypernetworks.get(hypernetwork))
                preview_path = extra_page.find_preview(path)
                if preview_path is None or dl_preview_image_overwrite:
                    if download_image_from_civitai(ModelType.Hypernetwork, hypernetwork, f"{path}.preview.{shared.opts.samples_format}"):
                        stats["Hypernetworks"]["img_success"] += 1
                    else:
                        stats["Hypernetworks"]["img_failed"] += 1
                else:
                    stats["Hypernetworks"]["img_skipped"] += 1
            
            description = download_description_from_civit(ModelType.Hypernetwork, hypernetwork, dl_markdown)
            if not overwrite:
                note = get_note(model_hash=get_model_sha256(ModelType.Hypernetwork, hypernetwork))
                if note != "":
                    stats["Hypernetworks"]["skipped"] += 1
                    continue
            if description != "":
                set_note(model_hash=get_model_sha256(ModelType.Hypernetwork, hypernetwork), note=description, model_type=ModelType.Hypernetwork)
                stats["Hypernetworks"]["success"] += 1
            else:
                stats["Hypernetworks"]["failed"] += 1

    if "Checkpoints" in model_types:
        checkpoints = checkpoint_tiles()
        if dl_preview_image:
            extra_page = ExtraNetworksPageCheckpoints()
        for checkpoint in pr.tqdm(checkpoints, desc="Downloading Checkpoint Descriptions", total=len(checkpoints), unit="checkpoints"):
            if dl_preview_image:
                path, ext = os.path.splitext(sd_models.checkpoints_list.get(checkpoint).filename)
                preview_path = extra_page.find_preview(path)
                if preview_path is None or dl_preview_image_overwrite:
                    if download_image_from_civitai(ModelType.Checkpoint, checkpoint, f"{path}.{shared.opts.samples_format}"):
                        stats["Checkpoints"]["img_success"] += 1
                    else:
                        stats["Checkpoints"]["img_failed"] += 1
                else:
                    stats["Checkpoints"]["img_skipped"] += 1
            
            description = download_description_from_civit(ModelType.Checkpoint, checkpoint, dl_markdown)
            if not overwrite:
                note = get_note(model_hash=get_model_sha256(ModelType.Checkpoint, checkpoint))
                if note != "":
                    stats["Checkpoints"]["skipped"] += 1
                    continue
            if description != "":
                set_note(model_hash=get_model_sha256(ModelType.Checkpoint, checkpoint), note=description, model_type=ModelType.Checkpoint)
                stats["Checkpoints"]["success"] += 1
            else:
                stats["Checkpoints"]["failed"] += 1

    if "LoRA" in model_types:
        loras = get_loras()
        if dl_preview_image:
            extra_page = ExtraNetworksPageLora()
        for lora_item in pr.tqdm(loras, desc="Downloading LoRA Descriptions", total=len(loras), unit="LoRAs"):
            if dl_preview_image:
                path, ext = os.path.splitext(lora.available_loras.get(lora_item).filename)
                preview_path = extra_page.find_preview(path)
                if preview_path is None or dl_preview_image_overwrite:
                    if download_image_from_civitai(ModelType.LoRA, lora_item, f"{path}.{shared.opts.samples_format}"):
                        stats["LoRA"]["img_success"] += 1
                    else:
                        stats["LoRA"]["img_failed"] += 1
                else:
                    stats["LoRA"]["img_skipped"] += 1
            
            description = download_description_from_civit(ModelType.LoRA, lora_item, dl_markdown)
            if not overwrite:
                note = get_note(model_hash=get_model_sha256(ModelType.LoRA, lora_item))
                if note != "":
                    stats["LoRA"]["skipped"] += 1
                    continue
            if description != "":
                set_note(model_hash=get_model_sha256(ModelType.LoRA, lora_item), note=description, model_type=ModelType.LoRA)
                stats["LoRA"]["success"] += 1
            else:
                stats["LoRA"]["failed"] += 1

    output_str = ""
    for key, value in stats.items():
        output_str += f"{key}: Descriptions: {value['success']} succeeded, {value['failed']} failed, and {value['skipped']} skipped. \nPreviews: {value['img_success']} succeeded, {value['img_failed']} failed, and {value['img_skipped']} skipped. | "
    return output_str

def get_textual_inversion_embeddings() -> List[str]:
    """
    Returns a list of all textual inversion embeddings names.
    
    :return: A sorted list of textual inversion embedding names.
    """
    embeddings = []
    for embedding in model_hijack.embedding_db.word_embeddings.values():
        embeddings.append(embedding.name)
    embeddings.sort()
    return embeddings

def get_hypernetworks() -> List[str]:
    """
    Retrieves the names of available hypernetworks.
    
    :return: A sorted list of hypernetwork names.
    """
    hypernetworks_names = list(shared.hypernetworks.keys())
    hypernetworks_names.sort()
    return hypernetworks_names

def get_loras() -> List[str]:
    """
    Retrieves the names of available LoRAs.
    
    :return: A list of LoRA names.
    """
    loras = []
    for name in lora.available_loras.keys():
        loras.append(name)
    return loras

def toggle_editing_markdown(visible: bool):
    """
    Toggles the markdown editor.

    :param visible: Whether the markdown editor is currently visible.
    :return: A tuple containing the new visibility and the updated button text.
    """
    visibility = not visible
    if shared.opts.model_note_autosave:
        btn_text = "Edit Markdown ✏️" if visible else "Finish 🏁" 
    else:
        btn_text = "Edit Markdown ✏️" if visible else "Save " + save_style_symbol 
    return visibility, gr.update(visible=visibility), gr.update(value=btn_text)

def export_note_to_disk(title: str, content: str, file_type: FileTypes, folder: Path, overwrite: bool) -> ResultType:
    """
    Exports the given content to a file on disk.

    :param title: The filename without extension.
    :param content: The content to be written into the file, converted to the correct format.
    :param file_type: The type of the file and content.
    :param folder: The directory where the file will be saved.
    :param overwrite: If True, the function will overwrite an existing file with the same name. If False, the function will return an error if the file already exists.
    :return: A `ResultType` indicating the outcome of the operation. This can be `ResultType.success` if the operation was successful, `ResultType.not_found` if the content is empty, or `ResultType.error` if an error occurred during the operation (such as if the file already exists and `overwrite` is False).
    """
    if content == "":
        return ResultType.not_found
    if file_type == FileTypes.HTML:
        content = convert_markdown_to_html(content)
    filepath = folder / f"{title}.{file_type.value[0]}"
    if not overwrite and filepath.exists():
        return ResultType.error
    try:
        with open(filepath, "w") as file:
            file.write(content)
    except Exception as e:
        print(f"Failed to save note: {e}")
        return ResultType.error
    return ResultType.success

def export_all_notes(file_type_picker, export_folder_checkbox, export_directory, export_name, export_folder_overwrite, pr=gr.Progress()):
    """
    Exports all notes to files on disk.

    :param file_type_picker: The chosen file type to export as.
    :param export_folder_checkbox: If True, notes will be saved in the same folder as their respective models. If False, all notes will be saved to a single directory specified by `export_directory`.
    :param export_directory: The directory where all the notes will be saved if `export_folder_checkbox` is False.
    :param export_name: The naming scheme for the exported files. If "Sha256", the files will be named after the sha256 hash of the model. Otherwise, they will be named after the model name.
    :param export_folder_overwrite: If True, the function will overwrite existing files with the same name. If False, the function will skip files that already exist.
    :param pr: A `gr.Progress` instance to monitor the progress of the operation.
    :return: A string summarizing the result of the operation, including the number of successful saves, missing notes, and failed saves.
    """
    if file_type_picker == "" or (not export_folder_checkbox and export_directory == "") or export_name == "":
        return "Please fill out all fields."
    stats = {ResultType.success: 0, ResultType.not_found: 0, ResultType.error: 0}
    def collect_stats(result : ResultType):
        stats[result] += 1
    file_type = FileTypes.from_description(file_type_picker)
    csv_data = []
    for embedding in pr.tqdm(model_hijack.embedding_db.word_embeddings.values(), desc="Saving Textual Inversion Notes", total=len(model_hijack.embedding_db.word_embeddings.values()), unit="embeddings"):
        sha256 = get_model_sha256(ModelType.Textual_Inversion, embedding.name)
        note = get_note(sha256)
        if not file_type == FileTypes.CSV:
            collect_stats(export_note_to_disk(title=sha256 if export_name == "Sha256" else embedding.name, content=convert_markdown_to_html(note) if file_type == FileTypes.HTML else note, file_type=file_type, folder=Path(embedding.filename).parent if export_folder_checkbox else Path(export_directory), overwrite=export_folder_overwrite))
        elif note != "":
            csv_data.append({"title" : sha256 if export_name == "Sha256" else embedding.name, "content" : convert_markdown_to_html(note) if file_type == FileTypes.HTML else note, "file_path" : embedding.filename})
            collect_stats(ResultType.success)
        else:
            collect_stats(ResultType.not_found)
    for name, path in pr.tqdm(shared.hypernetworks.items(), desc="Saving Hypernetwork Notes", total=len(shared.hypernetworks.items()), unit="hypernetworks"):
        sha256 = get_model_sha256(ModelType.Hypernetwork, name)
        note = get_note(sha256)
        if not file_type == FileTypes.CSV:
            collect_stats(export_note_to_disk(title=sha256 if export_name == "Sha256" else name, content=convert_markdown_to_html(note) if file_type == FileTypes.HTML else note, file_type=file_type, folder=Path(path).parent if export_folder_checkbox else Path(export_directory), overwrite=export_folder_overwrite))
        elif note != "":
            csv_data.append({"title" : sha256 if export_name == "Sha256" else name, "content" : convert_markdown_to_html(note) if file_type == FileTypes.HTML else note, "file_path" : path})
            collect_stats(ResultType.success)
        else:
            collect_stats(ResultType.not_found)
    for name, checkpoint  in pr.tqdm(sd_models.checkpoints_list.items(), desc="Saving Checkpoint Notes", total=len(sd_models.checkpoints_list.items()), unit="checkpoints"):
        sha256 = get_model_sha256(ModelType.Checkpoint, checkpoint.name_for_extra)
        note = get_note(sha256)
        if not file_type == FileTypes.CSV:
            collect_stats(export_note_to_disk(title=sha256 if export_name == "Sha256" else checkpoint.name_for_extra, content=convert_markdown_to_html(note) if file_type == FileTypes.HTML else note, file_type=file_type, folder=Path(checkpoint.filename).parent if export_folder_checkbox else Path(export_directory), overwrite=export_folder_overwrite))
        elif note != "":
            csv_data.append({"title" : sha256 if export_name == "Sha256" else checkpoint.name_for_extra, "content" : convert_markdown_to_html(note) if file_type == FileTypes.HTML else note, "file_path" : checkpoint.filename})
            collect_stats(ResultType.success)
        else:
            collect_stats(ResultType.not_found)
    for name, lora_on_disk in pr.tqdm(lora.available_loras.items(), desc="Saving LoRA Notes", total=len(lora.available_loras.items()), unit="LoRAs"):
        sha256 = get_model_sha256(ModelType.LoRA, name)
        note = get_note(sha256)
        if not file_type == FileTypes.CSV:
            collect_stats(export_note_to_disk(title=sha256 if export_name == "Sha256" else name, content=convert_markdown_to_html(note) if file_type == FileTypes.HTML else note, file_type=file_type, folder=Path(lora_on_disk.filename).parent if export_folder_checkbox else Path(export_directory), overwrite=export_folder_overwrite))
        elif note != "":
            csv_data.append({"title" : sha256 if export_name == "Sha256" else name, "content" : convert_markdown_to_html(note) if file_type == FileTypes.HTML else note, "file_path" : lora_on_disk.filename})
            collect_stats(ResultType.success)
        else:
            collect_stats(ResultType.not_found)
    if file_type == FileTypes.CSV:
        file_path = Path(export_directory) / 'notes.csv'
        if file_path.exists() and not export_folder_overwrite:
            save_location = f"Notes spreadsheet already exists at {file_path.absolute()} and overwrite is disabled"
        else:
            with open(file_path, 'w', newline='') as csvfile:
                # Create a new csv writer object
                writer = csv.writer(csvfile)
                if csv_data != []:
                    # Write the headers as the first row
                    headers = csv_data[0].keys()
                    writer.writerow(headers)
                # Write each row of data
                for row in csv_data:
                    writer.writerow(row.values())
            save_location = f"All notes were saved to {file_path.absolute()}"
    else:
        save_location = f"All notes where saved in the same folder as the model" if export_folder_checkbox else f"All models where saved to {Path(export_directory).absolute()}"
    return f"{save_location} || Saved Notes: {stats[ResultType.success]} | No Note: {stats[ResultType.not_found]} | Failed to Save Note: {stats[ResultType.error]}"

def import_note_from_disk(title: str, file_types: List[FileTypes], folder: Path) -> Union[ResultType, str]:
    """
    Imports a note from a file on disk.

    :param title: The filename without extension from which the note will be imported.
    :param file_types: A list of possible file types that will be tried in order until a file with a matching type is found.
    :param folder: The directory where the file is expected to be found.
    :return: A tuple where the first element is a `ResultType` indicating the outcome of the operation. This can be `ResultType.success` if the operation was successful, `ResultType.not_found` if no file was found with any of the given file types, or `ResultType.error` if an error occurred during the operation (such as a file read error). The second element is the content of the note if the operation was successful, or an error message if an error occurred, or an empty string if no file was found.
    """
    for file_type in file_types:
        filepath = folder / f"{title}.{file_type.value[0]}"
        if filepath.exists() and filepath.is_file():
            try:
                with open(filepath, 'r') as file:
                    content = file.read()
                    if file_type == FileTypes.HTML:
                        content = html2markdown.convert(content)
                return ResultType.success, content
            except Exception as e:
                return ResultType.error, str(e)
    return ResultType.not_found, ""

def import_all_notes(model_types, overwrite, import_name, import_folder_checkbox, import_directory, pr=gr.Progress()):
    """
    Imports all notes from files on disk to the corresponding models.

    :param model_types: A list of file types that the notes are stored in. The function will try to import the note from the file types in the given order until a file with a matching type is found.
    :param overwrite: If True, existing notes will be overwritten. If False, existing notes will be kept and new notes will be skipped.
    :param import_name: Determines whether the title of the file to import from is the SHA256 hash of the model or the name of the model. Must be either "Sha256" or "Name".
    :param import_folder_checkbox: If True, the function will look for the files in the same directory as the corresponding model. If False, the function will look for the files in the directory specified by `import_directory`.
    :param import_directory: The directory where the function will look for the files if `import_folder_checkbox` is False.
    :param pr: A progress bar object to display the progress of the operation.
    :return: A string summarizing the result of the operation, including the number of notes successfully imported, the number of notes not found, the number of existing notes skipped, and the number of notes that failed to import.
    """
    if model_types == []:
        return "No note types selected, nothing to import."
    if not import_folder_checkbox and import_directory == "":
        return "Please select a folder to import from."
    stats = {ResultType.success: 0, ResultType.not_found: 0, ResultType.skipped : 0, ResultType.error: 0}
    file_types = sorted([FileTypes.from_description(file_type) for file_type in model_types], key=lambda x: x.value[2], reverse=True)
    
    def collect_stats(result : ResultType):
        stats[result] += 1

    for embedding in pr.tqdm(model_hijack.embedding_db.word_embeddings.values(), desc="Importing Textual Inversion Notes", total=len(model_hijack.embedding_db.word_embeddings.values()), unit="embeddings"):
        sha256 = get_model_sha256(ModelType.Textual_Inversion, embedding.name)
        if not overwrite and get_note(sha256) != "":
            collect_stats(ResultType.skipped)
            continue
        result, note = import_note_from_disk(title=sha256 if import_name == "Sha256" else embedding.name, file_types=file_types, folder=Path(embedding.filename).parent if import_folder_checkbox else Path(import_directory))
        if note != "":
            set_note(model_hash=sha256, note=note, model_type=ModelType.Textual_Inversion)
        collect_stats(result)
    for name, path in pr.tqdm(shared.hypernetworks.items(), desc="Importing Hypernetwork Notes", total=len(shared.hypernetworks.items()), unit="hypernetworks"):
        sha256 = get_model_sha256(ModelType.Hypernetwork, name)
        if not overwrite and get_note(sha256) != "":
            collect_stats(ResultType.skipped)
            continue
        result, note = import_note_from_disk(title=sha256 if import_name == "Sha256" else name, file_types=file_types, folder=Path(path).parent if import_folder_checkbox else Path(import_directory))
        if note != "":
            set_note(model_hash=sha256, note=note, model_type=ModelType.Hypernetwork)
        collect_stats(result)
    for name, checkpoint in pr.tqdm(sd_models.checkpoints_list.items(), desc="Importing Checkpoint Notes", total=len(sd_models.checkpoints_list.items()), unit="checkpoints"):
        sha256 = get_model_sha256(ModelType.Checkpoint, checkpoint.name_for_extra)
        if not overwrite and get_note(sha256) != "":
            collect_stats(ResultType.skipped)
            continue
        result, note = import_note_from_disk(title=sha256 if import_name == "Sha256" else checkpoint.name_for_extra, file_types=file_types, folder=Path(checkpoint.filename).parent if import_folder_checkbox else Path(import_directory))
        if note != "":
            set_note(model_hash=sha256, note=note, model_type=ModelType.Checkpoint)
        collect_stats(result)
    for name, lora_on_disk in pr.tqdm(lora.available_loras.items(), desc="Importing LoRA Notes", total=len(lora.available_loras.items()), unit="LoRAs"):
        sha256 = get_model_sha256(ModelType.LoRA, name)
        if not overwrite and get_note(sha256) != "":
            collect_stats(ResultType.skipped)
            continue
        result, note = import_note_from_disk(title=sha256 if import_name == "Sha256" else name, file_types=file_types, folder=Path(lora_on_disk.filename).parent if import_folder_checkbox else Path(import_directory))
        if note != "":
            set_note(model_hash=sha256, note=note, model_type=ModelType.LoRA)
        collect_stats(result)
    return f"Imported Notes: {stats[ResultType.success]} | No Note: {stats[ResultType.not_found]} | Skipped existing notes {stats[ResultType.skipped]}| Notes failed to import: {stats[ResultType.error]}"

def on_ui_tabs() -> Tuple[gr.Blocks, str, str]:
    """
    Create the UI tab for model notes.
    
    :return: A tuple containing the UI tab for model notes.
    """
    supported_models = ["Textual Inversion", "Hypernetworks", "Checkpoints", "LoRA"]
    with gr.Blocks(analytics_enabled=False) as main_tab:
        for model in supported_models:
            with gr.Tab(model):
                with FormRow(elem_id="notes_mode_selection"):
                    with FormRow(variant='panel'):
                        if model == "Textual Inversion":
                            notes_model_select = gr.Dropdown(get_textual_inversion_embeddings(), elem_id="notes_embedding_model_dropdown", label="Select Textual Inversion", interactive=True)
                            create_refresh_button(notes_model_select, lambda: model_hijack.embedding_db.load_textual_inversion_embeddings(force_reload=True), lambda: {"choices": get_textual_inversion_embeddings()}, "refresh_notes_embedding_model_dropdown")
                        elif model == "Hypernetworks":
                            notes_model_select = gr.Dropdown(get_hypernetworks(), elem_id="notes__hypernetwork_model_dropdown", label="Select Hypernetwork", interactive=True)
                            create_refresh_button(notes_model_select, shared.reload_hypernetworks, lambda: {"choices": get_hypernetworks()}, "refresh_notes_hypernetwork_model_dropdown")
                        elif model == "LoRA":
                            notes_model_select = gr.Dropdown(get_loras(), elem_id="notes_lora_model_dropdown", label="Select LoRA", interactive=True)
                            create_refresh_button(notes_model_select, lora.list_available_loras, lambda: {"choices": get_loras()}, "refresh_notes_lora_model_dropdown")
                        elif model == "Checkpoints":
                            notes_model_select = gr.Dropdown(checkpoint_tiles(), elem_id="notes_lora_model_dropdown", label="Select Checkpoint", interactive=True)
                            create_refresh_button(notes_model_select, list_models, lambda: {"choices": checkpoint_tiles()}, "refresh_notes_lora_model_dropdown")
                    if shared.opts.model_note_markdown:
                        save_button = gr.Button(value="Edit Markdown ✏️", variant="secondary", elem_id="notes_markdown_toggle_button") # This leads to saving even when swapping to editing mode but that should be fine
                    elif not shared.opts.model_note_autosave:
                        save_button = gr.Button(value="Save changes " + save_style_symbol, variant="primary", elem_id="save_model_note")
                    civitai_button = gr.Button(value="Get description from Civitai", variant="secondary", elem_id="notes_civitai_button")
                if shared.opts.model_note_markdown:
                    with FormRow(elem_id="model_notes_textbox_container"):
                        note_box = gr.Textbox(label="Edit Markdown", max_lines=-1, elem_id="model_notes_textbox", placeholder="Make a note about the model selected above!", interactive=True, visible=False)
                        markdown = gr.Markdown(elem_id="model_notes_markdown")
                        note_box.change(fn=lambda mk: mk, inputs=[note_box], outputs=[markdown])
                        state_visible_toggle_button = gr.State(value=False)
                        save_button.click(fn=toggle_editing_markdown, inputs=[state_visible_toggle_button], outputs=[state_visible_toggle_button, note_box, save_button])
                else:
                    note_box = gr.Textbox(label="Note", lines=25, elem_id="model_notes_textbox", placeholder="Make a note about the model selected above!", interactive=False)
                if model == "Textual Inversion":
                    notes_model_select.change(fn=lambda select: on_model_selection(ModelType.Textual_Inversion, select), inputs=[notes_model_select], outputs=[note_box])
                    if shared.opts.model_note_autosave:
                        note_box.change(fn=lambda select, note: on_save_note(ModelType.Textual_Inversion, select, note), inputs=[notes_model_select, note_box], outputs=[])
                    else:
                        save_button.click(fn=lambda select, note: on_save_note(ModelType.Textual_Inversion, select, note), inputs=[notes_model_select, note_box], outputs=[])
                    civitai_button.click(fn=lambda select, note: on_civitai(ModelType.Textual_Inversion, select, note), inputs=[notes_model_select, note_box], outputs=[note_box])
                elif model == "Hypernetworks":
                    notes_model_select.change(fn=lambda select: on_model_selection(ModelType.Hypernetwork, select), inputs=[notes_model_select], outputs=[note_box])
                    if shared.opts.model_note_autosave:
                        note_box.change(fn=lambda select, note: on_save_note(ModelType.Hypernetwork, select, note), inputs=[notes_model_select, note_box], outputs=[])
                    else:
                        save_button.click(fn=lambda select, note: on_save_note(ModelType.Hypernetwork, select, note), inputs=[notes_model_select, note_box], outputs=[])
                    civitai_button.click(fn=lambda select, note: on_civitai(ModelType.Hypernetwork, select, note), inputs=[notes_model_select, note_box], outputs=[note_box])
                elif model == "LoRA":
                    notes_model_select.change(fn=lambda select: on_model_selection(ModelType.LoRA, select), inputs=[notes_model_select], outputs=[note_box])
                    if shared.opts.model_note_autosave:
                        note_box.change(fn=lambda select, note: on_save_note(ModelType.LoRA, select, note), inputs=[notes_model_select, note_box], outputs=[])
                    else:
                        save_button.click(fn=lambda select, note: on_save_note(ModelType.LoRA, select, note), inputs=[notes_model_select, note_box], outputs=[])
                    civitai_button.click(fn=lambda select, note: on_civitai(ModelType.LoRA, select, note), inputs=[notes_model_select, note_box], outputs=[note_box])
                elif model == "Checkpoints":
                    notes_model_select.change(fn=lambda select: on_model_selection(ModelType.Checkpoint, select), inputs=[notes_model_select], outputs=[note_box])
                    if shared.opts.model_note_autosave:
                        note_box.change(fn=lambda select, note: on_save_note(ModelType.Checkpoint, select, note), inputs=[notes_model_select, note_box], outputs=[])
                    else:
                        save_button.click(fn=lambda select, note: on_save_note(ModelType.Checkpoint, select, note), inputs=[notes_model_select, note_box], outputs=[])
                    civitai_button.click(fn=lambda select, note: on_civitai(ModelType.Checkpoint, select, note), inputs=[notes_model_select, note_box], outputs=[note_box])

        with gr.Tab("Civitai"):
            model_types = gr.CheckboxGroup(supported_models, label="Models", info="Select Model types to get descriptions for")
            overwrite = gr.Checkbox(label="Overwrite existing notes", info="Overwrite existing notes with Civitai descriptions")
            if shared.opts.model_note_markdown:
                dl_markdown = gr.Checkbox(value=True, label="Convert Html to Markdown", info="Convert Html to Markdown instead of removing it", interactive=True)
            else:
                dl_markdown = gr.Checkbox(value=False, label="Convert Html to Markdown", info="Convert Html to Markdown instead of removing it (Needs markdown support enabled in the settings)", interactive=False)
            with gr.Box():
                dl_preview_image = gr.Checkbox(value=True, label="Download preview image from Civitai", info="Download the first preview image from civitai that is then shown in the extra network tabs", interactive=True)
                dl_preview_image_overwrite = gr.Checkbox(value=False, label="Overwrite existing preview images", info="Overwrite existing preview images with images from civitai", interactive=True)
            get_all_button = gr.Button(value="Get all descriptions from Civitai", variant="primary")
            civit_stats = gr.Label(value="", label="Result")
            get_all_button.click(fn=on_get_all_civitai, inputs=[model_types, overwrite, dl_markdown, dl_preview_image, dl_preview_image_overwrite], outputs=[civit_stats])

        with gr.Tab("Import"):
            import_model_types = gr.CheckboxGroup([str(filetype) for filetype in FileTypes if not filetype == FileTypes.CSV], label="Import Formats", info="Select note types to import.\nIf a model as multiple note formats then only the most right selected format will be imported")
            with gr.Box():
                import_folder_checkbox = gr.Checkbox(label="Import from the models folder", info="Import notes from the folder where models are stored (ignored for csv)", value=True, elem_id="model_notes_import_folder_checkbox", interactive=True)
                import_directory = gr.Textbox(label="Import Directory Path", info="The folder where notes should be imported from", file_count="directory", elem_id="model_notes_import_folder_picker", visible=False, interactive=True)
                import_folder_checkbox.change(fn=lambda checkbox: gr.update(visible=not checkbox), inputs=[import_folder_checkbox], outputs=[import_directory])
            import_name = gr.Dropdown(["Model Name", "Sha256"], label="Import Filename", info="Select how the note files are named", value="Model Name", elem_id="model_notes_import_filename_formats", interactive=True, multiselect=False,  max_choice=1)
            import_overwrite = gr.Checkbox(label="Overwrite existing notes", info="Overwrite existing notes instead of skipping them", value=True)
            import_button = gr.Button(value="Import", variant="primary", elem_id="model_notes_import_button")
            import_stats = gr.Label(value="", label="Result")
            import_button.click(fn=import_all_notes, inputs=[import_model_types, import_overwrite, import_name, import_folder_checkbox, import_directory], outputs=[import_stats])

        with gr.Tab("Export"):
            file_type_picker = gr.Dropdown([str(filetype) for filetype in FileTypes], label="Export Format", value="Plaint text (*.txt)", elem_id="model_notes_export_formats", info="Select the format to convert the note to", interactive=True, multiselect=False, max_choice=1)
            with gr.Box():
                export_folder_checkbox = gr.Checkbox(label="Export into the models folder", info="Export notes in the same folder as the models (ignored for csv)", value=True, elem_id="model_notes_export_folder_checkbox", interactive=True)
                export_directory = gr.Textbox(label="Export Directory Path", info="The folder where the notes should be saved instead", file_count="directory", elem_id="model_notes_export_folder_picker", visible=False, interactive=True)
                export_folder_checkbox.change(fn=lambda checkbox: gr.update(visible=not checkbox), inputs=[export_folder_checkbox], outputs=[export_directory])
            export_name = gr.Dropdown(["Model Name", "Sha256"], label="Export Filename", info="Select how the note files should be named", value="Model Name", elem_id="model_notes_export_filename_formats", interactive=True, multiselect=False,  max_choice=1)
            export_folder_overwrite = gr.Checkbox(label="Overwrite existing notes", info="Overwrite existing note files instead of skipping them", value=True, elem_id="model_notes_export_overwrite", interactive=True)
            export_button = gr.Button(value="Export", variant="primary", elem_id="model_notes_export_button")
            export_stats = gr.Label(value="", label="Result")
            export_button.click(fn=export_all_notes, inputs=[file_type_picker, export_folder_checkbox, export_directory, export_name, export_folder_overwrite], outputs=[export_stats])

    return (main_tab, "Model Notes", "model_notes"),

def on_ui_settings() -> None:
    """
    Add our options to the UI settings page.

    :return: None
    """
    shared.opts.add_option("model_note_autosave", shared.OptionInfo(default=False, label="Enable autosaving edits in note fields", component=gr.Checkbox, section=("model-notes", "Model-Notes")))
    shared.opts.add_option("model_note_markdown", shared.OptionInfo(default=False, label="Enable Markdown support", component=gr.Checkbox, section=("model-notes", "Model-Notes")))
    shared.opts.add_option("model_note_hide_extra_note_preview", shared.OptionInfo(default=True, label="Hide extra model note preview", component=gr.Checkbox, section=("model-notes", "Model-Notes")))
    shared.opts.add_option("model_note_hide_extra_note_inject", shared.OptionInfo(default=False, label="Inject note into extra note preview", component=gr.Checkbox, section=("model-notes", "Model-Notes")))

def on_script_unloaded() -> None:
    """
    Close the database connection when the script is unloaded.

    :return: None
    """
    if conn:
        conn.close()

def overwrite_load_descriptions():

    def new_load_descriptions(self, path):
        if isinstance(self, ExtraNetworksPageTextualInversion):
            sha256 = get_model_sha256(ModelType.Textual_Inversion, os.path.basename(path))
            return get_note(sha256)
        elif isinstance(self, ExtraNetworksPageHypernetworks):
            sha256 = get_model_sha256(ModelType.Hypernetwork, os.path.basename(path))
            return get_note(sha256)
        elif isinstance(self, ExtraNetworksPageCheckpoints):
            sha256 = get_model_sha256(ModelType.Checkpoint, os.path.basename(path))
            return get_note(sha256)
        elif isinstance(self, ExtraNetworksPageLora):
            sha256 = get_model_sha256(ModelType.LoRA, os.path.basename(path))
            return get_note(sha256)
        else:
            return ""

    ui_extra_networks.ExtraNetworksPage.find_description = new_load_descriptions

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
        set_note(model_hash=shared.opts.sd_checkpoint_hash, note=note, model_type=ModelType.Checkpoint)

    def on_get_note(self) -> gr.update:
        """
        Get the note about the selected model and update it to the UI.
        
        :return: Gradio update setting the value to the note content and the lable to the models name.
        """
        note = get_note(shared.opts.sd_checkpoint_hash)
        return gr.update(value=note, label=f"Note on {shared.opts.sd_model_checkpoint}", lines=note.count("\n") + 1)

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
                    if shared.opts.model_note_markdown:
                        tex = gr.Textbox(label="Note", max_lines=-1, elem_id="model_notes_textbox", placeholder="Make a note about the model selected above!", visible=False, interactive=True)
                        tex_markdown = gr.Markdown(label="Note", elem_id="model_notes_markdown")
                        tex.change(fn=lambda mk: mk, inputs=[tex], outputs=[tex_markdown])
                    else:
                        tex = gr.Textbox(label="Note", lines=5, elem_id="model_notes_textbox", placeholder="Make a note about the model selected above!", interactive=True)
                if shared.opts.model_note_markdown:
                    state_visible_toggle_button = gr.State(value=False)
                    save_button = gr.Button(value="Edit Markdown ✏️", variant="secondary", elem_id="notes_markdown_toggle_button")
                    gr.Markdown(value="Nothing to see here", visible=False, elem_id="model_notes_markdown_template")
                    save_button.click(fn=toggle_editing_markdown, inputs=[state_visible_toggle_button], outputs=[state_visible_toggle_button, tex, save_button])
                if shared.opts.model_note_autosave:
                    tex.change(fn=self.on_save_note, inputs=[tex], outputs=[])
                else:
                    if not shared.opts.model_note_markdown:
                        save_button = gr.Button(value="Save changes " + save_style_symbol, variant="primary", elem_id="save_model_note")
                    else:
                        save_button = gr.Button(value="", variant="primary", elem_id="save_model_note", visible=False)
                    save_button.click(fn=self.on_save_note, inputs=[tex], outputs=[])
                update_button = ToolButton(value=notes_symbol, elem_id="model_note_update", visible=False)
                update_button.click(fn=self.on_get_note, inputs=[], outputs=[tex])