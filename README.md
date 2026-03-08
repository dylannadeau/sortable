# Categorization Tool

This tool helps you take messy lists — keywords, company names, product labels, anything — and organize them. Upload a spreadsheet or text file, and it will either **group similar items together** into meaningful categories or **standardize inconsistent names** so that "Acme Corp", "ACME LLC", and "Acme Inc." all resolve to one name. It runs in your browser on your own computer, and everything stays local to you.

---

## What you'll need

Before you start, make sure you have three things:

1. **Python 3.10 or newer** installed on your computer.
   If you're not sure whether you have it, don't worry — the setup steps below will tell you. If you need to install it, download it from [python.org/downloads](https://www.python.org/downloads/).

2. **An Anthropic API key.** This is what lets the tool use AI to name your groups and resolve tricky name matches. You can get one by creating a free account at [console.anthropic.com](https://console.anthropic.com/). Once you're logged in, go to **API Keys** and create a new key. Copy it somewhere safe — you'll paste it into the tool each time you use it.

3. **A terminal (command prompt).** This is a text window where you'll type a couple of commands.
   - **On Mac:** Open the app called **Terminal** (search for it in Spotlight, or find it in Applications → Utilities).
   - **On Windows:** Press the Windows key, type **cmd**, and open **Command Prompt**.

---

## Setup (one time only)

You only need to do these steps once. After that, you'll just repeat Step 4 each time you want to use the tool.

**Step 1:** Download or copy this entire project folder to your computer. Put it somewhere easy to find, like your Desktop or Documents folder.

**Step 2:** Open your terminal and navigate to the project folder. For example, if you put it on your Desktop:

```
cd ~/Desktop/sortable
```

On Windows, that would look like:

```
cd C:\Users\YourName\Desktop\sortable
```

**Step 3:** Install the required packages by running this command:

```
pip install -r requirements.txt
```

This will download everything the tool needs. It may take a few minutes the first time — that's normal.

**Step 4:** Start the tool:

```
streamlit run app.py
```

**Step 5:** Your browser should open automatically with the tool ready to use. If it doesn't, see the Troubleshooting section below.

---

## How to use it

### Keyword Bucketing

This tab is for grouping a list of items into themes. Upload a file containing your list — a spreadsheet with a column of keywords, a CSV export, or even a plain text file with one item per line. The tool will read your items, figure out which ones are related, and sort them into groups. It will also give each group a name that describes what the items have in common. You can control how many groups you want (or let it decide automatically) and how similar items need to be before they're grouped together. When it's done, you can download the results as a spreadsheet.

### Entity Standardization

This tab is for cleaning up a list where the same thing appears under different names. Upload your list, and the tool will find names that look like variations of each other and merge them under one standard name. If you already have a "master list" of correct names, you can upload that too — the tool will match your messy list against it. If you don't have a master list, it will pick the most common version of each name as the standard. You can adjust how strict the matching is, and whether to ignore common business suffixes like LLC and Inc.

---

## Your API key is private

When you open the tool, it asks you to paste your Anthropic API key. Here's what you should know:

- A **session** lasts as long as you have the tool open in your browser. Once you close the tab or stop the tool in your terminal, the session ends and the key is gone.
- Your key is **never saved to disk** — it's only held in memory while you're using the tool. Nothing is written to any file.
- Each time you open the tool, you'll need to paste your key again. If you'd like to avoid looking it up each time, consider keeping it in a secure notes app or password manager.

---

## Troubleshooting

**"I get an error about Python not being found"**
This usually means Python isn't installed, or your computer can't find it. Visit [python.org/downloads](https://www.python.org/downloads/) and install the latest version. On Windows, make sure to check the box that says **"Add Python to PATH"** during installation. After installing, close your terminal, open a new one, and try again.

**"The browser doesn't open automatically"**
That's fine — it just means your system didn't auto-launch it. Look in your terminal for a line that says something like `Local URL: http://localhost:8501`. Copy that address and paste it into your browser's address bar.

**"My API key says it's invalid"**
Double-check that you copied the full key (it starts with `sk-ant-`). Make sure there are no extra spaces before or after it. If it still doesn't work, go to [console.anthropic.com](https://console.anthropic.com/), check that your key is still active, and make sure your account has available credit.

**"The tool is slow on large files"**
Files with more than a few thousand rows take longer to process — that's expected. The first run is also slower because the tool needs to download a small language model in the background (about 80 MB, one time only). If you're working with very large files (10,000+ rows), consider breaking them into smaller batches.

**"I see an error I don't understand"**
Try these steps in order: (1) Close the browser tab. (2) In your terminal, press `Ctrl+C` to stop the tool. (3) Run `streamlit run app.py` again to restart it. If the error keeps happening, take a screenshot — it will help if you need to ask someone for help.
