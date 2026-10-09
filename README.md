# Data cleaning app for exported data

# Language
Python
# Dependencies

Ollama
pandas

## Input
A .zip, or text file

## Output

The same file but where all text data is anonymized according to GDPR.

## Method

The system goes through all files, and for each text file
with standard measures anonymize all e-mail addresses, personal identifiable data such names, locations, phone numbers except for Brand words we need to arhive
The stripped files is stored in the same file structure with other binary files as the uploaded zip.

The Ollama model is used to verify this.

# Requirements
* MUST RUN completely local. No network operations. To align with data protection.
* PyPI package structure

* Show disclaimer when running tool it is an aid but not warranty and the user is still responsible. This tool is not using any external services
Arguments with standard python arguments library:
* Default to output the same file name but with the stripped data in text files. Use -o to specify custom output directory.
* Can be auto accepted with -y.
* Arg for model.
* Creates an audit trail log of everything it did with row numbers and operations in an .audit.log file (location can be customized with a flag)
* Can be run in supervised mode (default), each file cleaning is shown as a diff the user has to accept, amend or reject.

To agent: Write a CI actions workflow which trigger each commit to main, it should build the project, create binaries and installers such .deb/.rpm, PYPI, .msi, .exe and publish them as artifacts and push them to the Releases section.
Do the same for a develop branch which creates same for unstable and beta builds.
