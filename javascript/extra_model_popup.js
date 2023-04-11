let model_notes_isPopupOpen = false;

// Save note using API
async function model_notes_saveNote(model_type, name) 
{
  const note = document.getElementById("model_note_extra_model_textbox").value;
  const url = `/model_notes/set_note_by_name?type=${encodeURIComponent(model_type)}&name=${encodeURIComponent(name)}&note=${encodeURIComponent(note)}`;

  try {
    const response = await fetch(url, { method: "POST" });
    const data = await response.json();
  } catch (error) {
    console.error(error);
  }
}

// Get note using API
async function model_notes_getNote(name, model_type) {
  const response = await fetch(`/model_notes/get_note_by_name?name=${name}&type=${model_type}`);
  const data = await response.json();
  return data.note;
}

// Open popup animation
function model_notes_openPopup(popup) {
  const popupOverlay = popup.querySelector("#popupOverlay");
  const popupContent = popup.querySelector("#popupContent");

  setTimeout(() => {
    popupOverlay.style.backgroundColor = "rgba(0, 0, 0, 0.8)";
    popupContent.style.transform = "scale(1)";
    popupContent.style.opacity = "1";
  }, 50);
}

// Close popup animation
function model_notes_closePopup(popup) {
  const popupOverlay = popup.querySelector("#popupOverlay");
  const popupContent = popup.querySelector("#popupContent");

  popupOverlay.style.backgroundColor = "rgba(0, 0, 0, 0)";
  popupContent.style.transform = "scale(0.9)";
  popupContent.style.opacity = "0";
  setTimeout(() => {
    document.body.style.overflow = "auto";
    document.body.removeChild(popup);
    model_notes_isPopupOpen = false; // Reset the flag
  }, 150);
}

// Create a popup containing a textbox
async function note_extra_models_create_popup(name, model_type) {
  if (model_notes_isPopupOpen) return; // Prevent opening multiple popups

  model_notes_isPopupOpen = true;
  const icons = document.querySelectorAll('#model_note_extra_model_icon');
  icons.forEach(icon => {
    icon.style.cursor = 'progress';
    });
  document.body.style.cursor = 'progress'; // Change cursor to loading

  setTimeout(async () => {
    // Fetch note from API
    try {
      const note = await model_notes_getNote(name, model_type);
      document.body.style.cursor = 'auto'; // Change cursor back to normal
      model_notes_create_actual_popup(name, model_type, note);
      icons.forEach(icon => {
        icon.style.cursor = 'pointer';
        });
    } catch (error) {
      console.error(error);
      document.body.style.cursor = 'auto'; // Change cursor back to normal
      model_notes_isPopupOpen = false; // Reset the flag
      icons.forEach(icon => {
        icon.style.cursor = 'pointer';
        });
    }
  }, 0);
}


function model_notes_create_actual_popup(name, model_type, note) 
{
  // Create required elements
  const popup = document.createElement("div");
  const popupOverlay = document.createElement("div");
  const popupContent = document.createElement("div");
  const popupTitle = document.createElement("h2");
  const closeButton = document.createElement("div");
  const textBox = document.createElement("textarea");
  const container = document.createElement("div");

  // Get styles
  const txt2imgTextarea = document.querySelector("#txt2img_prompt textarea");
  const styles = window.getComputedStyle(txt2imgTextarea);
  const backgroundColor = (styles.getPropertyValue('background-color') === 'rgba(0, 0, 0, 0)') ? 'white' : styles.getPropertyValue('background-color');
  const color = styles.getPropertyValue('color');
  const borderColor = styles.getPropertyValue('border-color');
  const borderRadius = styles.getPropertyValue('border-radius');

  // Set up popup overlay
  popupOverlay.id = "popupOverlay";
  popupOverlay.style.cssText = "position: fixed; top: 0; left: 0; width: 100%; height: 100%; background-color: rgba(0,0,0,0); z-index: 9999; display: flex; align-items: center; justify-content: center; backdrop-filter: blur(3px); transition: background-color 0.3s ease;";
  popupOverlay.addEventListener("click", (event) => {
    if (event.target === popupOverlay) {
      model_notes_closePopup(popup);
    }
  });

  // Set up popup content
  popupContent.id = "popupContent";
  popupContent.style.cssText = `position: relative; background-color: ${backgroundColor}; border-radius: 5px; padding: 3vw; box-shadow: 0px 0px 2vw rgba(0, 0, 0, 0.5); overflow: auto; max-height: 90vh; width: 75%; display: block; transform: scale(0.9); opacity: 0; transition: transform 0.3s ease, opacity 0.3s ease;`;

  // Set up popup title
  popupTitle.id = "popupTitle";
  popupTitle.textContent = `Notes for ${name}`;
  popupTitle.style.cssText = `text-align: center; color: ${color}; font-family: Arial, sans-serif; font-size: 2.5vw;`;

  // Set up close button
  closeButton.id = "closeButton";
  closeButton.innerHTML = "&times;";
  closeButton.style.cssText = "position: absolute; top: 0%; right: 1.5vw; color: #aaa; font-size: 5vw; cursor: pointer; transition: color 0.3s;";
  closeButton.addEventListener("mouseenter", () => closeButton.style.color = "#f44336");
  closeButton.addEventListener("mouseleave", () => closeButton.style.color = "#aaa");
  closeButton.addEventListener("click", () => model_notes_closePopup(popup));

  // Set up text box
  textBox.id = "model_note_extra_model_textbox";
  textBox.className = "scroll-hide";
  textBox.setAttribute("data-testid", "textbox");
  textBox.style.cssText = `overflow-y: scroll; height: ${Math.min(0.75 * window.innerHeight, Math.max(0.25 * window.innerHeight, 84))}px; width: 100%; background-color: ${backgroundColor}; color: ${color}; border-color: ${borderColor}; border-radius: ${borderRadius}; border-style: solid; overflow: visible;`;
  textBox.textContent = note;

  // Set up container
  container.style.cssText = "display: flex; flex-direction: column; justify-content: center; align-items: center; height: 100%;";

  const saveModelNoteElement = document.getElementById("save_model_note");
  if (saveModelNoteElement) 
  {
    // Create save button
    const saveButton = document.getElementById("txt2img_generate").cloneNode(true);

    // Set up save button
    saveButton.id = "saveButton";
    saveButton.textContent = "Save";
    saveButton.style.cssText = `${styles.cssText}; width: 100%; height: ${document.getElementById("txt2img_generate").clientHeight}px; cursor: pointer; margin-top: 10px;`;

    // Add event listeners
    saveButton.addEventListener("mouseenter", () => saveButton.style.cursor = "pointer");
    saveButton.addEventListener("mouseleave", () => saveButton.style.cursor = "auto");
    saveButton.addEventListener("click", async () => {
      await model_notes_saveNote(model_type, name);
    });

    // Append elements
    container.appendChild(saveButton);
  }
  else
  {
    textBox.addEventListener("input", async () => {
      await model_notes_saveNote(model_type, name);
    });
}

  popupContent.appendChild(popupTitle);
  popupContent.appendChild(closeButton);
  popupContent.appendChild(textBox);
  popupContent.appendChild(container);
  popupOverlay.appendChild(popupContent);
  popup.appendChild(popupOverlay);

  // Add popup to the body
  document.body.appendChild(popup);
  document.body.style.overflow = "hidden";

  // Open the popup
  model_notes_openPopup(popup);

  // Resize title font size on window resize
  window.addEventListener("resize", () => {
    popupTitle.style.fontSize = `${popup.clientWidth * 0.025}px`;
  });
};