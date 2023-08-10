# AnkiChinese

Scrape the ArchChinese dictionary to generate Anki flashcards with:
- Pinyin & Audio
- Definitions
- Common examples
- Formation/Origin
- Stroke order diagrams
- HSK level

# Installation

    pip install ankichinese

# Usage

    ankichinese

    -h, --help                  Show help message and exit 

    -csv                        Output to CSV instead of Anki deck    
    --input, -i INPUT           Input file with characters to scrape (default: input.txt)
    --output, -o OUTPUT         Name of output file (do not include extension) 
                                (default: ankichinese_output)

    --defs, -d NUM              Number of definitions to scrape per character (default: 5)
    --examples, -e NUM          Number of example words to scrape per character (default: 3)

## Generate New AnkiChinese Deck
How to create an entirely new Anki deck with the name `ankichinese_output.apkg` in the current directory using custom AnkiChinese styling. 

1. Create `input.txt` with the characters you want to scrape (avoid non-Chinese characters).
2. Run `ankichinese`.
3. Open Anki and import `ankichinese_output.apkg`.

### Updating is Easy
Just run `ankichinese` again with new characters in `input.txt` and import the new `ankichinese_output.apkg` file into Anki. Anki will automatically update the existing deck without losing progress.

## Update Existing (Non-AnkiChinese) Deck Without Losing Progress

1. Prepare current deck for export
    1. Decide what information you would like to add from the AnkiChinese deck.
    2. Create empty fields in your deck for the information you want to add.
2. Export the deck you want to update from Anki using Notes in Plain Text (.txt) format. Make sure to check the `Include unique identifier` box.
3. Open your deck in Excel or Google Sheets
    1. Excel
        1. Go to the `Data` -> `From Text/CSV` and import the exported deck file.
        2. Set `File Origin` to `65001: Unicode (UTF-8)` and `Delimiter` to `Tab` and click `Load`.
    2. Google Sheets
        1. Go to `File` -> `Import` -> `Upload` and select the exported deck file. 
        2. Set separator type to `Tab` and click `Import data`.
    3. Copy the entire column of Chinese characters into `input.txt`.
4. Run `ankichinese -csv`
5. Open both your exported deck and the `ankichinese_output.csv` file in Excel or Google Sheets. (Use the same method as before)
6. Sort both tables by the column containing Chinese characters.
7. Copy your desired information from the `ankichinese_output.csv` table into your exported deck table. Do not add/delete columns or modify the GUID column of your deck.
8. Save the file as a .csv file and import into Anki.

# Credits
Stroke order diagrams:
- Online stroke order diagrams: https://hanziwriter.org/
- Offline stroke order font: https://rtega.be/chmn/index.php?subpage=68

Chinese audio:
- https://yoyochinese.com/chinese-learning-tools/Mandarin-Chinese-pronunciation-lesson/pinyin-chart-table
- Neutral tones: https://www.purpleculture.net/chinese_pinyin_chart/