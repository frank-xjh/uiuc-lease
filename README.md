# astrbot-plugin-lease-price

AstrBot plugin for showing UIUC lease prices from supported landlord websites.

## Commands

- `/price`
  Lists all supported providers.
- `/price <provider>`
  Fetches floor plan names and starting prices for the provider.

## Supported providers

- `The Cottages`

## Current output

The plugin currently returns:

- provider heading
- full floor plan name
- bed and bath layout
- starting monthly price

## Data source

- The Cottages floorplans: <https://thecottagesillinois.com/floorplans/>

## Notes

- Prices are fetched directly from the provider website at runtime.
- HTTP requests are made with `httpx`.
- The plugin keeps a short in-memory cache to reduce repeated requests.
- If the provider page changes its HTML structure, the parser may need an update.
