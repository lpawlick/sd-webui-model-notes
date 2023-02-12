// Hover hints for every element we add

// Hints mapped to element ids
model_notes_titles = 
{
    "notes_model_dropdown" : "Select a Stable-Diffusion Model to write a Note for",
    "refresh_notes_model_dropdown" : "Refresh the list of Stable-Diffusion Models",
    "save_model_note" : "Save the Note",
    "model_notes_textbox" : "Note for the selected Model",
    "model_notes_tool" : "Show/Hide the note",
    "setting_model_note_autosave": "Hides the save button and autosaves every edit resulting more database write attempts. Needs a restart to take effect"
}

onUiUpdate(function()
{
    // Iterate over every hint
    Object.entries(model_notes_titles).forEach(([key, value]) => 
    {
        // In case we have several objects with the same id, we iterate over all found elements
        gradioApp().querySelectorAll(`#${key}`).forEach(function(element)
        {
            tooltip = model_notes_titles[element.id];
            if(tooltip)
            {
                element.title = tooltip;
            }
        })
    });

    // Unused, since we don't have any hints for dropdown elements
	/*gradioApp().querySelectorAll('select').forEach(function(select)
    {
        if (select.onchange != null) return;
        select.onchange = function()
        {
            select.title = model_notes_titles[`${select.id}_${select.value}`] || "";
        }
	});
    */
})
