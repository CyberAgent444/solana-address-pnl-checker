# Solana Insider Checker

Before running the script, make sure to add your helius.dev API key on the 8th line of the main Python file.

This project is designed for advanced Solana memecoin traders who want a quick, clean way to check if a Solana wallet is portable. It’s not a strategy tool – it's simply a faster method to spot potential insiders.

## Features

- Generates a clean HTML report that summarizes a wallet's PNL.
- Automatically accesses the Dexscreener chart for the desired token with the maker already included.
- Provides a simple web interface for entering a Solana wallet address.
- Opens the report in a browser for a quick review.

## Installation

To install all required libraries in one go, run:

``` pip install requests flask ```

*(Note: Libraries such as threading and webbrowser are part of the Python standard library.)*

## Usage

1. **Configure the API Key:**  
   Edit the main Python script and insert your helius.dev API key on the 8th line.

2. **Run the Script:**  
   Ensure that the Python script and the `run.bat` file are in the same folder.  
   Simply execute the `run.bat` file to start the server and open the web interface.

3. **Generate Report:**  
   - Input the desired Solana wallet address in the web interface.
   - The script fetches transactions, processes PNL data, and generates an HTML report.
   - Click on a token in the report to open its Dexscreener chart with the maker parameter already set.

This tool is built purely to make it easier and faster to check wallet portability – no strategies, just finding insiders wallets.

Happy trading.
