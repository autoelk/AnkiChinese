# AnkiChinese

Scrape the ArchChinese dictionary to generate Anki flashcards with:
1. Pinyin & Audio
2. Definitions
3. Common examples
4. Stroke order diagrams
5. HSK level

## 1. Installation

    pip install ankichinese

## 2. Usage

    ankichinese

    -h, --help                  Show help message and exit 

    --input, -i INPUT           Input file with characters to scrape (default: input.txt)
    --output, -o OUTPUT         Name of output file (do not include extension) 
                                (default: ankichinese_output)
    --type, -t {anki,csv}       Output file type (default: anki)

    --defs, -d NUM              Number of definitions to scrape per character (default: 5)
    --examples, -e NUM          Number of example words to scrape per character (default: 3)

## Credits
Online stroke order diagrams: https://hanziwriter.org/
Offline stroke order font: https://rtega.be/chmn/index.php?subpage=68

Chinese audio:
1. https://yoyochinese.com/chinese-learning-tools/Mandarin-Chinese-pronunciation-lesson/pinyin-chart-table
2. https://www.purpleculture.net/chinese_pinyin_chart/