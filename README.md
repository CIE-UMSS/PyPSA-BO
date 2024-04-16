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
    

## How to setup the model

We are currently working on automating the process but **for the time being** the process involves downloading the current version of PyPSA-Earth and swapping the list of files and data provided in this repository with the predefined folders downloaded for PyPSA-Earth. 

To automatically download and configure the scripts, data and files used to run the Bolivian case in the PyPSA-Earth submodule you should:

1. Make sure to create a local clone of the repository (including the files in the submodule). This can be done by downloading the files from github or with a gitmanager tool such as smargit, gitkraken or others.


2. Install the minimum packages to run the pyhton script in charge of the setup, as defined in the file "environment_setup". This can be done manually with pip or conda or by executing the command in the prompt if you have conda (make sure to open the comand in the same folder where PyPSA-BO is located):

3. Run the script in the main folder named "setup.py". After this you should be able to see that files in your local submodule have been added and/or changed compared to their initial download, allowing you to directly run the Bolivian case with PyPSA-Earth

## How to run the model

To run the case for the Bolivian system it is necessary to go through the installation process of PyPSA-Earth (explained in more detail in their own repository). Given that in this case we are using the model and its repository as a submodule you should consider these minor changes compared to the normal installation of PyPSA-Earth:

* Install a virtual environment for the submodule by navigating in the terminal to the pypsa-earth folder and execute the following command:

         ...pypsa-bo/pypsa-earth % conda env create -f envs/environment.yaml

* After this you should be able to run the model by typing in the terminal the following commands:

        ...pypsa-bo/pypsa-earth % snakemake -j 1 solve_all_networks -n
        
    This will create a dry run of the model (check if all scripts are being recognized)

        ...pypsa-bo/pypsa-earth % snakemake -j 1 solve_all_networks
    
    This will run the model up until the final task/rule that it has to execute (solve_all_networks)

        ...pypsa-bo/pypsa-earth % snakemake -j 1 solve_all_networks --forceall

    This will force the model to run all scripts that can be run (particularly useful if changes in the configuration or other scritps have been made)

Finally, some caviats are to be considered regarding the execution of the model: 
* The current version of PyPSA-BO is working with a submodule corresponding to v0.3 of PyPSA-Earth, therefore, different version might have some compatibility issues (which shouldn't be hard to solve, but will need debugging).
* For running the model, we recommend using gurobi (v10.0.3) which has been used so far, so a license has to be aquired and properly installed beforehand.
* The data provided for Bolivia (cutout, costs, powerplants, lines, etc.) is facilitated to avoid the user to redownload and adapt information manually. However, all this can be done by enabling the initial rules in the workflow of PyPSA-Earth, setting up your own licenses and configure files as you prefer.