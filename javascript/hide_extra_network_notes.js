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
                    hide_extra_network_notes_refresh_setup(); // Setup for the refresh button
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

function hide_extra_network_notes_refresh_setup() 
{
    // Select the container for all embedding cards and take the parent of the parent which gets a "pending" class when the cards are refreshed
    const element = document.getElementById('txt2img_textual_inversion_cards').parentElement.parentElement;

    // Create a new MutationObserver
    const observer = new MutationObserver(function(mutationsList) {
    for (let mutation of mutationsList) 
    {
        if (
            mutation.type === 'attributes' &&
            mutation.attributeName === 'class' &&
            !element.classList.contains('pending') &&
            mutation.oldValue && mutation.oldValue.includes('pending')
        ) 
        {
        // "pending" class has been removed, hide any new note previews
        hide_extra_network_notes();
        break;
        }
    }
    });

    // Start observing the class attribute for changes
    observer.observe(element, { attributes: true, attributeOldValue: true });
}

window.addEventListener('load', function() 
{
    if (opts.model_note_hide_extra_note_preview)
    {
        model_notes_hide_extra_network_notes_setup();
    }
});