# AnkiChinese

This program scrapes the ArchChinese dictionary to generate Anki flashcards.

## 1. Installation

    pip install ankichinese

## 2. Usage

    ankichinese

### 2.1 Optional Arguments:

    -h, --help                  Show help message and exit 

    --input, -i INPUT           Input file with characters to scrape (default: input.txt)
    --output, -o OUTPUT         Name of output file (do not include extension) 
                                (default: ankichinese_output)
    --type, -t {anki,csv}       Output file type (default: anki)

    --numDefs, -d NUM           Number of definitions to scrape per character (default: 5)
    --numExamples, -e NUM       Number of example words to scrape per character (default: 3)