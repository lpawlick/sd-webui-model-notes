# Settings

The Model-Notes section in the settings page allows you to configure the following:

![The checkbox about autosaving note changes](../images/settings_autosaving.png)

If autosaving is enabled then the note will be saved everytime a change is made to a note, otherwise it will only be saved when the save button is clicked.

![The checkbox about enabling markdown support](../images/settings_markdown.png)

If this option is enable then the note will be rendered as markdown and add a markdown editor, otherwise it will just render plaint text.

![The checkbox about showing a note preview](../images/hide_extra_preview.png)

If this option is enabled then note preview in the extra model notes section will be hidden, otherwise it will show a preview of the note on the extra model card itself.
The preview will be loaded from the local file notes file next to the model by default unless injection is enabled. Only affects the previews shown in in the extra network section.

![The checkbox about injecting the note preview](../images/settings_injecting_extra_preview.png)

Replaces the note preview with a note from the model notes extensions. This should always be on unless you have a reason to show the local note file next to the model over the note saved in model notes. Only affects the previews shown in in the extra network section.
