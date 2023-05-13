// Store the previous checkpoint hash value
function setup_note_extra_models()
{
    // Get all elements with class "card"
    const cardElements = document.getElementsByClassName("card");

    // Loop through each card element
    Array.from(cardElements).forEach(card => 
    {
        // Create a new Gradio button container element
        const buttonContainer = document.createElement("div");
        buttonContainer.style.position = "absolute";
        buttonContainer.style.top = "10px";
        buttonContainer.style.left = "10px";

        // Create a span element for the emoji
        const emojiSpan = document.createElement("span");
        emojiSpan.innerHTML = "&#x1F4DD;"; // set emoji content to pencil emoji
        emojiSpan.style.fontSize = "30px"; // increase emoji size
        emojiSpan.style.transition = "transform 0.1s, background-color 0.1s"; // add transition effect
        emojiSpan.style.borderRadius = "5px"; // set border radius
        emojiSpan.style.paddingLeft = "2.5px"; // set padding on the left side
        emojiSpan.style.backgroundColor = "transparent"; // set transparent background color
        emojiSpan.id = "model_note_extra_model_icon";

        // Add hover effect to the button container
        const onMouseOver = () => 
        {
            emojiSpan.style.backgroundColor = "rgba(0, 128, 255, 0.2)"; // set background color
            emojiSpan.style.transform = "scale(1.1)"; // scale up the size
        };
        const onMouseOut = () => 
        {
            emojiSpan.style.backgroundColor = "transparent"; // set transparent background color
            emojiSpan.style.transform = "scale(1)"; // reset the size
        };
        buttonContainer.addEventListener("mouseover", onMouseOver);
        buttonContainer.addEventListener("mouseout", onMouseOut);

        // Append the emoji span element to the button container element
        buttonContainer.appendChild(emojiSpan);

        // Add click event listener to the button container
        const onClick = event => 
        {
            event.stopPropagation(); // stop event propagation

            // Get the "name" div element
            const nameDiv = card.querySelector(".actions .name");
            // Get the text content of the "name" div
            const nameText = nameDiv.textContent;

            // Get the selected tab text
            const selectedTabText = card.closest('[id*="_extra_tabs"]').querySelector('.tab-nav .selected').textContent;

            // Call the create_popup function with the name and selected tab text as arguments
            note_extra_models_create_popup(nameText, selectedTabText);

            // Set the background color of the emoji span to the hover color of the card
            emojiSpan.style.backgroundColor = "rgba(0, 128, 255, 0.2)";
        };
        buttonContainer.addEventListener("click", onClick);

        // Append the button container element to the card element
        card.appendChild(buttonContainer);
    });
}

function model_notes_extra_model_button_setup()
{
    // Create a new Intersection Observer instance for the extra network tabs
    const observer = new IntersectionObserver((entries, observer) => 
    {
        entries.forEach(entry => 
            {
                // Check if the element is intersecting/visible
                if (entry.isIntersecting) 
                {
                    // Add the note button to the model cards
                    setup_note_extra_models();
                    model_notes_extra_model_button_refresh_setup(); // Setup for the refresh button
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

function model_notes_extra_model_button_refresh_setup() 
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
        // "pending" class has been removed, readd the note button to new cards
        setup_note_extra_models();
        break;
        }
    }
    });

    // Start observing the class attribute for changes
    observer.observe(element, { attributes: true, attributeOldValue: true });
}

window.addEventListener('load', function() 
{
    model_notes_extra_model_button_setup();
});