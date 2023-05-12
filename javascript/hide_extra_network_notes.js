function hide_extra_network_notes()
{
    // Get all descriptions from the extra network notes
    const descriptionElements = document.getElementsByClassName('description');

    // Loop through the elements and hide them
    for (let i = 0; i < descriptionElements.length; i++) {
    const element = descriptionElements[i];
    element.style.display = 'none';
    }

}

window.addEventListener('load', function() 
{
    if (opts.model_note_hide_extra_note_preview)
    {
        hide_extra_network_notes();
    }
});