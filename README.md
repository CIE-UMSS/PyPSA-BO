# PyPSA-BO
This is the main repository of PyPSA-BO, a PyPSA-Earth model curated for Bolivia.

This repository currently consists on a set of folders and a file with a link to download country specific data:

* The folder "Result_analysis" contains a set of two jupyter notebooks that help with post-processing and reviewing the results of the simulation done with the model. 
    - Before running the files make sure that the paths have been set to the proper locations in your local installation to avoid errors 
* The folder "Modified_files" considers the files that have been adapted from the predefined version of PyPSA-Earth to work specifically for the Bolivian case study:
    * the "scripts" folder considers all the scripts that were modified and have to be incorporated/replaced
    * the "envs" folder considers the environment dependencies required to run the model (with particular versions for solvers and libraries to avoid compatibility issues)
    * the files "config", "config.default", "snakefile" are defined to run the current working version of PyPSA-BO (modifying them would lead to alternative results)
* The file "Link_for_data" has the url location from which you can download data sets generated and populated both from online repositories and country specific information
    * Data should be extracted automatically and added to the respective locations but it can also be included manually
    

## How to run the model

We are currently working on automating the process but for the time being the process involves downloading the current version of PyPSA-Earth and swapping the list of files and data provided in this repository with the predefined folders downloaded for PyPSA-Earth. 