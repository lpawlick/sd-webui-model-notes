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

function model_notes_hide_extra_network_notes_setup()
{
    // Create a new Intersection Observer instance for the extra network tabs
    const observer = new IntersectionObserver((entries, observer) => 
    {
        entries.forEach(entry => 
            {
                // Check if the element is intersecting/visible
                if (entry.isIntersecting) 
                {
                    // Hide the note previews
                    hide_extra_network_notes();
                    
                    // We only need to hide note previews once so remove the observer
                    observer.unobserve(entry.target);
                }
        });
    });

    // Get all elements with the class "extra-networks"
    const elements = document.querySelectorAll('.extra-networks');

    // Observe each element
    elements.forEach(element => {
        observer.observe(element);
    });
}
window.addEventListener('load', function() 
{
    if (opts.model_note_hide_extra_note_preview)
    {
        model_notes_hide_extra_network_notes_setup();
    }
});