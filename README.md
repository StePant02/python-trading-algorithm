# python-trading-algorithm
# Automated Crypto Scalper API Bot (Alpha Version)

An automated, data-driven algorithmic trading script written in Python. This project is currently in the Alpha phase and operates fully functionally in paper-trading mode via REST API integrations with major cryptocurrency exchanges (e.g., Bybit, Hyperliquid).

##  Project Overview
The goal of this script is to analyze market trends and execute rapid scalping strategies based on technical indicators (including ADX, DMI, and EMA). The core focus of the current Alpha version is absolute system stability, precise data handling, and zero-crash execution under heavy load.

## Algorithmic thought behind the project
This project is designed and in development specifically for scalping trading. It is composed of two (2) core algorithms: the first acts as the "radar" (market scanning and signal detection), and the second is the execution script. The current focus is on maximizing execution efficiency and maintaining absolute API stability under load.

##  Performance & Stability Metrics
System reliability is heavily tested. The script has undergone rigorous QA stability sessions:
* Analyzed **150-200 hours** of execution logs.
* Achieved a continuous **5-day (120-hour) stress test** with 100% uninterrupted runtime and zero execution crashes.
* Successfully handled API rate limits, connection timeouts, and data routing without memory leaks.

##  Tech Stack
* **Language:** Python
* **Integration:** REST APIs 
* **Architecture:** Modular design for easy indicator updates and error handling.

##  Contributing
Since this project is in active development, community contributions are highly encouraged! I am specifically looking for feedback and pull requests in the following areas:
* **Latency Optimization:** Reducing the execution time between the signal and the API order placement.
* **Indicator Logic:** Fine-tuning the mathematical calculations for DMI (currently analyzing 24-unit differentials) and EMA to reduce false positives.
* **Advanced Error Handling:** Hardening the script against unexpected exchange-side API downtimes.
* I am currently balancing the development of this algorithmic script with my university engineering studies. Because time is tight, any community pull requests, feedback, or optimization ideas are highly appreciated!

Feel free to open an Issue or submit a Pull Request.

##  Disclaimer
This software is for educational purposes and paper trading only. It does not constitute financial advice. Use at your own risk.

##  License & Copyright
Copyright (c) 2026 StePant02

This project is licensed under the MIT License which is included. 
This means you are free to use, copy, modify, merge, publish, and distribute this software, provided that the original copyright notice and permission notice are included in all copies or substantial portions of the software. 

**Please note:** The software is provided "as is", without warranty of any kind. The author holds no liability for any financial losses or damages incurred through the use of this script.
