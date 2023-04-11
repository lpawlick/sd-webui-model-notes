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

window.onload = function() {
    setup_note_extra_models();
};