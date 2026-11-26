# NFL pre-lock outdoor weather

NFL staging matches the ordered FanDuel contest matchups to the Eastern-date schedule and verifies venue name, venue ID and indoor designation. The NWS point lookup resolves both hourly and same-run gust data at reviewed outdoor venues. The capture starts at the forecast interval containing kickoff and covers the next three hours. Forecast issue time, download time, exact source URLs and contest digest are stored in a downloadable JSON receipt. The decision cutoff is capped at the earliest scheduled kickoff among all matched contest games.

The initial reviewed venues are Highmark Stadium and Acrisure Stadium for outdoor forecasts, Ford Field for fixed indoor status and AT&T Stadium for a retractable roof requiring a game-specific confirmation. Other venues explicitly require a venue check. The stadium area forecast does not measure conditions on the field.

On November 26, 2026 the live contest 137123 weather review matched all three Thanksgiving games. For Kansas City at Buffalo, the November 26 3:57 a.m. ET NWS update had 37°F, rain with a 100% precipitation probability, 13 mph sustained wind and about 35 mph gusts in the 8 p.m. hour around the 8:20 p.m. ET kickoff. Source inputs were read before the 1 p.m. ET first kickoff. The forecast continued to show rain and lower gusts over the remaining three hours. Detroit was classified as fixed indoor. Dallas remained unconfirmed for the event-specific roof position.

The staging review flags precipitation probability of at least 50%, sustained wind of at least 15 mph or gusts of at least 25 mph. These thresholds trigger a qualitative passing, kicking and game script review. No automatic projection or lineup changes are included. Missing wind, gust, temperature or precipitation values are shown as unknown. Freshness means the forecast was updated within 24 hours of the recorded observation. The receipt shows the observation time for pre-lock refreshes. A stale forecast or an ambiguous or incomplete schedule cannot generate a verified pre-lock receipt for an outdoor game.

- [NFL official Thanksgiving schedule](https://media.nfl.com/football-information/2026/weekly-preview---capsules-/week-12-nfl-preview---capsules-)
- [NWS hourly Highmark Stadium grid](https://api.weather.gov/gridpoints/BUF/39,42/forecast/hourly)
- [NWS Highmark Stadium gust grid](https://api.weather.gov/gridpoints/BUF/39,42)
- [Buffalo Bills open-air stadium announcement](https://www.buffalobills.com/news/how-to-watch-the-bills-ribbon-cutting-ceremony-at-highmark-stadium)
- [NFL Dallas media guide](https://static.www.nfl.com/league/apps/league-site/media-guides/2025/DAL.pdf)
