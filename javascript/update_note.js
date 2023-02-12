// Store the previous checkpoint hash value
let previousCheckpointHash = opts.sd_checkpoint_hash;

function setup_note_interval()
{
  setInterval(function() 
  {
    // When a new model was selected, update the note
    if (opts.sd_checkpoint_hash !== previousCheckpointHash) 
    {
      previousCheckpointHash = opts.sd_checkpoint_hash;
      triggerOnCheckpointChange();
    }
  }, 500); // Check every 500 ms
}

function triggerOnCheckpointChange() 
{
  // Create an update event and update notes in every tab
  gradioApp().querySelectorAll('#model_note_update').forEach(function(refresh_button) 
  {
    refresh_button.click();
  });
}

// Wait until all DOM Content is loaded before checking for new models
document.addEventListener('DOMContentLoaded', setup_note_interval);