let model_notes_isPopupOpen = false;

// Save note using API
async function model_notes_saveNote(model_type, name, note) 
{
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
  const response = await fetch(`/model_notes/get_note_by_name?name=${encodeURIComponent(name)}&type=${encodeURIComponent(model_type)}`);
  const data = await response.json();
  return data.note;
}

// Convert markdown to HTML
async function model_notes_convert_markdown_to_html(markdown) 
{
  const response = await fetch(`/model_notes/utils/convert_markdown_to_html?text=${encodeURIComponent(markdown)}`);
  const data = await response.json();
  return data.html;
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

// Updates the extra model note preview
function model_notes_extra_model_inject_new_description(note, card)
{
  const description = card.querySelector(".description")
  description.innerHTML = note;
}

// Create a popup containing a textbox
async function note_extra_models_create_popup(name, model_type, card) 
{
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
      model_notes_create_actual_popup(name, model_type, note, true, card);
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


function model_notes_create_actual_popup(name, model_type, note, markdown, card) 
{
  // Create required elements
  const popup = document.createElement("div");
  const popupOverlay = document.createElement("div");
  const popupContent = document.createElement("div");
  const popupTitle = document.createElement("h2");
  const closeButton = document.createElement("div");
  const textBox = document.createElement("textarea");
  const textContainer = document.createElement("div");
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
  textBox.style.cssText = `overflow-y: scroll; min-height: ${Math.min(0.75 * window.innerHeight, Math.max(0.25 * window.innerHeight, 84))}px; width: 100%; background-color: ${backgroundColor}; color: ${color}; border-color: ${borderColor}; border-radius: ${borderRadius}; border-style: solid; overflow: visible;`;
  textBox.textContent = note;
  textBox.style.flex = "1";

  // Set up container
  container.style.cssText = "display: flex; flex-direction: column; justify-content: center; align-items: center; height: 100%;";

  const saveModelNoteElement = document.getElementById("save_model_note");
  const markdownTemplate = document.getElementById("model_notes_markdown_template")
  if (markdownTemplate)
  {
    // Hide Textbox by default
    textBox.style.visibility = "hidden";

    // Create Markdown button
    const markdownButton = document.getElementById("txt2img_generate").cloneNode(true);

    // Set up Markdown button
    markdownButton.id = "model_notes_markdown_btn";
    markdownButton.textContent = "Edit ✏️";
    markdownButton.style.cssText = `${styles.cssText}; width: 100%; height: ${document.getElementById("txt2img_generate").clientHeight}px; cursor: pointer; margin-top: 10px;`;

    // Add event listeners
    markdownButton.addEventListener("mouseenter", () => markdownButton.style.cursor = "pointer");
    markdownButton.addEventListener("mouseleave", () => markdownButton.style.cursor = "auto");
    markdownButton.addEventListener("click", async () => 
    {
      const text = markdownButton.textContent.trim();
      const markdownContainer = document.getElementById("model_notes_markdown_container");

      if (text === "Edit ✏️") 
      {
        markdownButton.textContent = saveModelNoteElement ? "Save 💾" : "Finish 🏁";
        markdownContainer.style.maxWidth = "50%";
        textBox.style.visibility = "visible";
      } 
      else 
      {
        if (saveModelNoteElement)
        {
          await model_notes_saveNote(model_type, name, textBox.value);
          if (!opts.model_note_hide_extra_note_preview)
          {
            model_notes_extra_model_inject_new_description(textBox.value, card);
          };
        }
        markdownContainer.style.maxWidth = "100%";
        textBox.style.visibility = "hidden";
        markdownButton.textContent = "Edit ✏️";
      }
    });

    // Append elements
    container.appendChild(markdownButton);
  }
  else if (saveModelNoteElement) 
  {
    // Create save button
    const saveButton = document.getElementById("txt2img_generate").cloneNode(true);

    // Set up save button
    saveButton.id = "model_notes_saveButton";
    saveButton.textContent = "Save";
    saveButton.style.cssText = `${styles.cssText}; width: 100%; height: ${document.getElementById("txt2img_generate").clientHeight}px; cursor: pointer; margin-top: 10px;`;

    // Add event listeners
    saveButton.addEventListener("mouseenter", () => saveButton.style.cursor = "pointer");
    saveButton.addEventListener("mouseleave", () => saveButton.style.cursor = "auto");
    saveButton.addEventListener("click", async () => {
      await model_notes_saveNote(model_type, name, textBox.value);
      if (!opts.model_note_hide_extra_note_preview)
      {
        model_notes_extra_model_inject_new_description(textBox.value, card);
      };
    });

    // Append elements
    container.appendChild(saveButton);
  }
  if (!saveModelNoteElement)
  {
    textBox.addEventListener("input", async () => 
    {
      await model_notes_saveNote(model_type, name, textBox.value);
      model_notes_extra_model_inject_new_description(textBox.value, card);
    });
}

  textContainer.appendChild(textBox);
  if (markdownTemplate)
  {
    const markdownContainer = document.createElement("div");
    markdownContainer.className = document.querySelector("#model_notes_markdown_template").className.replace("hidden", "").trim();
    markdownContainer.id = "model_notes_markdown_container";
    markdownContainer.style.color = color;
    markdownContainer.style.marginLeft = "1vw";
    markdownContainer.style.marginRight = "1vw";
    
    textContainer.style.display = "flex";
    textContainer.style.flexDirection = "row";
    textContainer.style.justifyContent = "center";
    textContainer.appendChild(markdownContainer);
    textBox.addEventListener("input", async () => 
    {
      const new_html = await model_notes_convert_markdown_to_html(textBox.value);
      markdownContainer.innerHTML = new_html;

      // Apply CSS style to images within markdownContainer
      const images = markdownContainer.getElementsByTagName("img");
      for (let img of images) 
      {
        img.style.maxWidth = "100%";
        img.style.height = "auto";
      }
    });
    textBox.dispatchEvent(new Event('input')); // Sets the markdown text
  }

  popupContent.appendChild(popupTitle);
  popupContent.appendChild(closeButton);
  popupContent.appendChild(textContainer);
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