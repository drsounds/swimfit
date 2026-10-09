# Data cleaning app for exported data

# Environment
Python, Ollama and pandas

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
* PyPI package
* Show disclaimer when running tool it is an aid but not warranty and the user is still responsible. Can be auto accepted with -y.
