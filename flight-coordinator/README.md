# ✈ Flight Coordinator — Google Sheets Template

A Google Apps Script that generates a fully-formatted Google Sheets workbook for comparing round-trip flight options between two travelers on the **same day**, across **different airlines**.

## What It Does

| Tab | Purpose |
|-----|---------|
| **✈ Flight Options** | Enter up to 6 flight option pairs (outbound + return) for Person A and Person B, including layovers and prices |
| **📊 Timeline** | Visual 30-minute-block Gantt chart to see when each person is in-air, on layover, or on the ground — and where those windows overlap |
| **📋 Summary** | Side-by-side scorecard and final decision tracker |

### Key Features

- **6 side-by-side option slots** for each traveler
- **Outbound + Layover + Return** rows per option
- **In-air overlap detection** — see when both travelers are flying at the same time
- **Layover coordination** — see when one person's layover aligns with the other's in-air window
- **Combined price tracking** per option pair
- **Final decision box** with booking confirmation fields and meetup notes
- Color-coded by traveler (blue = Person A, red = Person B)

## Quick Start

1. Go to [script.google.com](https://script.google.com) and create a new project
2. Delete the default `myFunction` code
3. Paste the contents of `Code.gs`
4. Click **Run → createFlightCoordinator**
5. Authorize permissions when prompted
6. A link to your new spreadsheet appears in the execution log and a popup

## How to Use the Timeline Tab

The **📊 Timeline** tab shows a 6 AM → midnight grid in 30-minute blocks.

1. After entering times in **✈ Flight Options**, go to the Timeline tab
2. Color cells covering each flight's in-air window:
   - **Blue** = Person A in air
   - **Red** = Person B in air
   - **Yellow** = both in air (overlap)
   - **Light blue** = Person A layover
   - **Pink** = Person B layover
   - **Green** = layovers coincide
3. Fill in the **Overlap & Coordination Analysis** table at the bottom

## Timeline Color Key

| Color | Meaning |
|-------|---------|
| 🔵 Dark Blue | Person A — In Air |
| 🔴 Dark Red | Person B — In Air |
| 🟡 Yellow | Both In Air (Overlap) |
| 💙 Light Blue | Person A — Layover |
| 🩷 Pink | Person B — Layover |
| 🟢 Green | Layovers Coincide |

## Coordination Scenarios to Watch For

- **Both in air simultaneously** → neither can communicate; plan ahead
- **A is on layover while B is flying** → A can track B's flight, be available on landing
- **B is on layover while A is flying** → B can plan airport logistics while waiting
- **Layovers coincide** → both waiting; can video call or coordinate together

## Customizing

- Rename **Person A / Person B** to actual names in the script before running
- Change `startHour = 6` in `buildTimelineSheet()` if flights start earlier than 6 AM
- Increase the `6` in the option loops to add more comparison slots

## File Structure

```
flight-coordinator/
├── Code.gs       # Google Apps Script — run this to create the spreadsheet
└── README.md     # This file
```

## License

MIT — free to use, share, and adapt.
