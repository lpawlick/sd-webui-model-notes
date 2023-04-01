import launch

if not launch.is_installed("beautifulsoup4"): # Dependencies for removing html elements from notes 
    launch.run_pip("install beautifulsoup4==4.12.0", "Requirements for Model Notes")