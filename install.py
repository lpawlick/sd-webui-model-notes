import launch

if not launch.is_installed("beautifulsoup4"): # Dependencies for removing html elements from notes 
    launch.run_pip("install beautifulsoup4==4.12.0", "Requirements for Model Notes")
if not launch.is_installed("html2markdown"): # Dependencies for converting html elements to markdown in notes
    launch.run_pip("install html2markdown==0.1.7 ", "Requirements for Model Notes")