# Health Monitor Dashboard --- Design Guide

> A practical UI specification for a hardware-connected
> health-monitoring dashboard across mobile, tablet, and desktop. The
> visual reference is the supplied VITAL / MONITOR concept: quiet
> neutrals, restrained teal status color, clear typography, thin
> borders, and an ECG trace that earns the strongest color on screen.

## 1. Product intent

### Purpose

Show the few measurements an operator needs to understand current sensor
readings and whether the hardware is connected:

-   Heart rate, in beats per minute (bpm)
-   Peripheral oxygen saturation (SpO₂, %)
-   Body temperature (°C)
-   A continuously updating ECG waveform
-   Connection and signal-quality state for the relevant hardware
    modules

The interface is a monitoring surface, not a medical decision engine. Do
not imply that the dashboard diagnoses conditions or replaces clinical
equipment. Do not label readings "normal" or "safe" unless thresholds
have been validated for the device, intended population, and use case.
Prefer neutral labels such as "Within configured range" only when real
configured limits exist.

### Design principles

1.  **Readings before decoration.** Values, units, timestamps, and
    connection state are the content.
2.  **One visual hierarchy.** The current value is prominent; label and
    unit are secondary; status is tertiary.
3.  **Use color with meaning.** Neutral surfaces by default. Color is
    reserved for connection, signal state, warnings, and the ECG trace.
4.  **No ornamental UI.** No gradients, glass effects, decorative blobs,
    oversized empty hero areas, emoji, or unnecessary illustrations.
5.  **Honest live state.** Distinguish live hardware readings from demo,
    stale, disconnected, or unavailable data.
6.  **Responsive by composition.** Rearrange content to fit the
    viewport; do not merely shrink a desktop layout.
7.  **Accessible at a glance.** Never use color alone to communicate
    state.

## 2. Information architecture

### Persistent header

-   Product label: `VITAL / MONITOR`
-   Hardware connection state: `Device connected`, `Reconnecting`, or
    `Device disconnected`
-   Last successful data update, with local time and clear stale state
-   Optional device identifier when multiple devices are supported

Do not add profile avatars, greeting text, marketing copy,
notifications, or a large navigation menu unless the product actually
needs them.

### Main content order

1.  **Overview heading** --- `Patient overview` or the product's chosen
    neutral heading, plus a short line such as
    `Live readings from connected sensors`.
2.  **Vital readings** --- heart rate, SpO₂, body temperature.
3.  **ECG** --- live waveform, time scale, amplitude scale, signal
    quality, and pause/resume control if supported.
4.  **Sensor status** --- pulse oximeter, temperature probe, ECG module,
    each with a text state.
5.  **Optional event/history area** --- only if the hardware or product
    genuinely records events. Keep it below live monitoring.

Avoid adding cards for data that can be shown as a simple row. Do not
show fabricated patient identity, age, diagnosis, trends, or readings.

## 3. Layout and responsive behavior

Use content-driven CSS Grid/Flexbox rather than fixed coordinates. The
following breakpoints are starting points, not device detection rules.
Adjust them when real content or testing shows the layout needs to
change.

  -----------------------------------------------------------------------
  Viewport                Layout                  Main behavior
  ----------------------- ----------------------- -----------------------
  Small mobile: 320--479  Single column           Header wraps cleanly;
  px                                              vital readings stack;
                                                  ECG remains full width;
                                                  sensor status becomes a
                                                  compact list

  Large mobile: 480--767  Single column, optional Keep ECG full width;
  px                      2-up vitals when each   avoid narrow waveform
                          card remains readable   plots

  Tablet: 768--1023 px    Two-column vital grid;  Do not squeeze the ECG
                          ECG full width; sensor  into a narrow side
                          status below or beside  panel
                          ECG if space allows     

  Desktop: 1024--1439 px  Three vital cards in    ECG gets roughly 2.5--3
                          one row; ECG and sensor times the width of the
                          status in a two-column  status panel
                          section                 

  Wide desktop: 1440 px   Same hierarchy with a   Increase whitespace
  and above               centered max-width      slightly; do not
                          container               stretch cards and text
                                                  across the entire
                                                  screen
  -----------------------------------------------------------------------

### Container and spacing

-   Page max-width: `1440px` recommended; center the content on wide
    displays.
-   Desktop horizontal padding: `32px`--`48px`.
-   Tablet horizontal padding: `24px`.
-   Mobile horizontal padding: `16px`; never let content touch the
    viewport edge.
-   Main section gap: `24px` desktop/tablet, `16px` mobile.
-   Card internal padding: `24px` desktop, `20px` tablet, `16px` mobile.
-   Keep vertical rhythm consistent. Use a spacing scale rather than
    arbitrary one-off values.
-   Respect safe-area insets on devices with display cutouts.

### Mobile composition

-   Header: product label on the first line; connection state and
    last-update details can wrap to a second line. Keep the state
    visible without horizontal scrolling.
-   Vital cards: stack by default in this order: heart rate, SpO₂,
    temperature. A two-column arrangement is acceptable only above a
    width where labels, values, and units do not wrap awkwardly.
-   ECG: full width, with a useful minimum plot height of approximately
    `220px`; provide horizontal time-window controls only if the user
    needs them.
-   Sensor status: simple rows with sensor name, textual state, and
    optional last-seen time.
-   Do not use a fixed desktop sidebar on mobile. If navigation is
    needed later, use a compact top navigation or a small bottom
    navigation with text labels.
-   Touch targets should be at least `44 × 44px`. Do not rely on hover
    to reveal controls.

### Tablet composition

-   Use a 2-column vital grid when card widths remain comfortable.
-   Keep the ECG plot across the full content width on portrait tablets.
-   On landscape tablets, a 2:1 ECG/status split is acceptable if the
    plot still has enough width to show waveform detail.
-   Avoid large empty areas caused by desktop-sized cards in a short
    viewport.

### Desktop composition

-   Three vital cards share one row with equal visual weight.
-   Below them, use a wide ECG panel and a narrower sensor-status panel.
-   ECG should occupy approximately 68--75% of the available row width;
    status uses the remainder.
-   Keep the header compact. The page title should not compete with the
    current measurements.
-   At high zoom or when the window narrows, allow the layout to
    transition naturally to tablet rules.

## 4. Visual system

### Color tokens

Use a light theme as the default to match the reference. Store colors as
tokens; do not scatter raw hex values across components.

  --------------------------------------------------------------------------
  Token                      Suggested value         Use
  -------------------------- ----------------------- -----------------------
  `--color-page`             `#F3F5F6`               Page background

  `--color-surface`          `#FFFFFF`               Cards and header
                                                     surface

  `--color-text`             `#172235`               Primary text and values

  `--color-text-secondary`   `#586579`               Supporting text and
                                                     units

  `--color-text-muted`       `#778294`               Metadata only; maintain
                                                     readable contrast

  `--color-border`           `#D8DEE5`               Card outlines and
                                                     dividers

  `--color-grid-minor`       `#F0E6E6`               ECG minor grid

  `--color-grid-major`       `#E6D4D4`               ECG major grid

  `--color-accent`           `#008F72`               Connected state and
                                                     restrained emphasis

  `--color-accent-soft`      `#E2F4EF`               Subtle live/status
                                                     background

  `--color-ecg`              `#E52B2B`               ECG waveform only

  `--color-warning`          `#A86400`               Warning state, paired
                                                     with text

  `--color-danger`           `#B42318`               Error/disconnected
                                                     critical state, paired
                                                     with text

  `--color-focus`            `#245DDB`               Keyboard focus ring
  --------------------------------------------------------------------------

These are starting tokens. Validate text and component contrast against
WCAG 2.2 AA before release. Do not reduce contrast to preserve a subtle
aesthetic.

### Color rules

-   Use a white surface on a very light cool-gray page.
-   Prefer a thin neutral border over a visible shadow. If a shadow is
    necessary, keep it subtle and consistent.
-   Green/teal means a confirmed connection or a configured positive
    state---not a general decoration.
-   Red is reserved for the ECG waveform and genuine error states. Do
    not make every chart, button, and status red.
-   Amber indicates a warning that needs attention. Include text such as
    `Signal weak`; color alone is insufficient.
-   Avoid gradients, neon accents, rainbow charts, tinted backgrounds on
    every card, and decorative color blobs.

### Typography

Use the existing product font if one is already established. Otherwise
choose a highly legible sans-serif such as `Inter`, `Source Sans 3`, or
the system UI stack. Do not load several font families.

Suggested scale: - Page title: `32px / 38px`, weight `650`--`700`
desktop; `26px / 32px` mobile. - Vital value: `48px`--`56px`, weight
`650`--`700` desktop; `40px`--`48px` mobile. - Section/card title:
`18px / 24px`, weight `600`. - Body and sensor rows: `15px`--`16px`,
weight `400`--`500`. - Metadata and timestamps: `13px`--`14px`; do not
go smaller for essential state. - Units: `18px`--`20px`, normal weight,
secondary color.

Use tabular numerals for changing measurements to prevent visual jitter.
Keep labels short and specific. Avoid all-caps body copy, exaggerated
letter spacing, and using bold for every line.

### Shape and elevation

-   Card radius: `6px`--`10px`; use one shared radius token.
-   Inputs and buttons: `6px`--`8px`.
-   Pills: only for compact status labels when useful; do not turn every
    label into a pill.
-   Border: `1px solid var(--color-border)`.
-   Elevation: default to no shadow; reserve a slight shadow for
    overlays only.
-   Do not nest cards inside cards. Use section headings and dividers
    instead.

## 5. Vital reading cards

Each card contains: 1. A clear label. 2. A value with a fixed unit. 3.
Optional state text based on a configured rule. 4. Optional timestamp
when freshness cannot be inferred from the global header.

Example structure:

``` text
Heart rate                         bpm
72
Within configured range
```

### Measurement rules

-   Heart rate: display `bpm`; do not display an unexplained percentage
    or arbitrary trend arrow.
-   SpO₂: display `%`; use the typographic form `SpO₂` with a real
    subscript where supported.
-   Temperature: display `°C`; preserve the sensor's actual precision
    instead of inventing decimals.
-   Use an em dash for unavailable readings, with adjacent text such as
    `No reading` or `Sensor disconnected`.
-   Do not present a stale value as live. Show the value only with a
    visible stale state, or replace it with an unavailable state
    according to product requirements.
-   Keep units visually attached to their value and expose the complete
    label/value/unit to assistive technology.
-   Do not hard-code clinical thresholds into UI components. Thresholds
    and interpretation belong to validated device/product configuration.

### Change and alert behavior

-   Update the displayed number without flashing the whole card.
-   Do not animate values with rolling odometers or bounce effects.
-   If a reading crosses a configured threshold, show a clear textual
    state and use the defined warning/error color.
-   Avoid alarm sounds, auto-dismissed warnings, or alerting behavior
    unless explicitly required and validated.

## 6. ECG waveform

The waveform is the main data visualization. It must remain legible and
honest rather than decorative.

### Plot structure

-   Give the plot the largest continuous area in the dashboard.
-   Include a subtle ECG-style grid with minor and major lines.
-   Label the vertical axis in `mV` and the horizontal axis in seconds.
-   Show calibration/sweep information only when it matches the actual
    acquisition configuration, e.g. `25 mm/s` and `10 mm/mV`. Never
    display these as fixed claims if the hardware settings differ.
-   Provide a short signal state such as `Good signal`, `Weak signal`,
    `Lead off`, or `No signal`, based on actual module data.
-   A `LIVE` label is allowed only while fresh samples are arriving.
-   Keep the trace visually distinct from the grid. Do not use area
    fills, gradients, glow, shadows, or a decorative pulse animation.

### Live rendering

-   Render incoming samples at a stable cadence. Buffer samples and
    update the plot efficiently; avoid a full page re-render for every
    sample.
-   Use a rolling time window suitable for the acquisition rate and use
    case. Make the time window explicit if the user can change it.
-   If samples are missing, show a gap or a visible signal interruption.
    Do not draw a plausible line across missing data.
-   If the stream stops, stop the live indicator and show the last
    update time and a stale/disconnected message.
-   Do not synthesize a heartbeat to make the dashboard look active.
-   If downsampling is needed, preserve peaks and clinically relevant
    waveform morphology; document the method and validate it against the
    source signal.
-   Keep the graph responsive: the plot should resize with its container
    without distorting time or amplitude scales.
-   Support reduced motion. A static or paused waveform must remain
    understandable.

### ECG controls

Only include controls that the hardware and implementation support: -
Pause/resume visual scrolling without stopping data acquisition. - Time
window selection, if useful. - Export or record controls only if data
storage and consent/security behavior are implemented.

Label whether pause affects display only or the actual recording stream.
Never imply that acquisition stopped when only animation paused.

## 7. Hardware and connection status

Use a compact list, not a separate decorative card for each module.

Recommended row: - Sensor/module name - Text state: `Connected`,
`Reconnecting`, `Disconnected`, `No data`, or `Error` - Optional
`Last data received` timestamp when relevant

Connection states must come from hardware/transport telemetry, not from
a static green dot. Include text next to any status color.

Suggested state mapping: - Connected and fresh: teal indicator +
`Connected` - Reconnecting: amber indicator + `Reconnecting` -
Disconnected: red indicator + `Disconnected` - Connected but no fresh
samples: amber indicator + `No recent data` - Module error: red
indicator + concise actionable message

Do not show "all systems normal" unless every required sensor has a
verified current state. Make the global device state consistent with
individual module states.

## 8. Iconography

Use a consistent outline icon family. Recommended: **Lucide**
(`lucide-react` for React projects), with a consistent stroke width of
`1.75` or `2`.

Use icons sparingly and only where they improve recognition: - Heart
rate: `HeartPulse` - SpO₂ / pulse oximeter: `Activity` or `Waves` -
Temperature: `Thermometer` - ECG module: `Activity` - Connection:
`Cable` or `Wifi` only if it accurately describes the connection type -
Timestamp/history: `Clock3` - Warning: `TriangleAlert` - Error:
`CircleAlert` - Settings: `Settings2` - Pause/resume: `Pause` / `Play` -
Expand chart: `Maximize2`

Rules: - No emoji, emoji-like illustrations, mixed icon libraries, or
arbitrary Unicode symbols as icons. - Do not add an icon to every label
just to fill space. - Icons must have accessible names when interactive;
decorative icons should be hidden from assistive technology. - Pair
icon-only controls with a tooltip and an accessible label. Tooltips must
not be the only accessible name. - Keep icon sizes consistent: `16px`
for inline metadata, `18px`--`20px` for controls, up to `22px` for a
meaningful section icon. - Do not use icons as the only indicator of
connection, alert, or sensor state.

## 9. Interaction and feedback

-   Controls should look interactive only when they work.
-   Use a visible keyboard focus ring; do not remove outlines without
    replacement.
-   Provide hover, focus, pressed, disabled, and loading states where
    relevant.
-   Avoid gratuitous transitions. Use short `120ms`--`180ms` transitions
    for color and border changes; do not animate layout or measurement
    cards unnecessarily.
-   Respect `prefers-reduced-motion`.
-   Use inline feedback for connection and stream changes. Avoid toast
    notifications for routine incoming readings.
-   If a connection fails, explain what happened and offer a real retry
    action when available.
-   Do not use a fake loading skeleton while data is already available.
-   Distinguish `Loading`, `No data received`, `Disconnected`, and
    `Error`; these are different states.

## 10. Accessibility and safety

-   Target WCAG 2.2 AA.
-   Ensure text contrast of at least 4.5:1 for normal text and 3:1 for
    large text; validate meaningful UI boundaries and focus indicators
    too.
-   All actions must be keyboard accessible and have visible focus.
-   Use semantic headings in order, landmarks, and real buttons for
    actions.
-   Give chart controls and status updates accessible names. Provide a
    text alternative or data summary for the ECG chart; do not rely on
    the visual trace alone.
-   Avoid announcing every ECG sample through a screen reader. Announce
    meaningful status changes and provide a separate accessible summary.
-   Do not communicate status using color alone.
-   Respect browser zoom and text resizing up to 200% without clipping
    or loss of function.
-   Support narrow screens and landscape orientation without horizontal
    page scrolling.
-   Treat health readings as sensitive data. Do not log or expose them
    unnecessarily; secure transport and storage where applicable.
-   Display a clear disclaimer appropriate to the product's validated
    use. A student prototype should be labelled as a prototype and not
    for clinical decision-making.

## 11. Data states and edge cases

Design and test all of the following, not just the successful live
state:

-   Initial connection in progress
-   Connected, waiting for first sample
-   Fresh data from every sensor
-   One sensor disconnected while others continue
-   Entire device disconnected
-   Reconnection attempt
-   Stale readings
-   Invalid, out-of-range, or malformed sensor payload
-   ECG lead off or poor signal quality
-   Data gaps or irregular sample arrival
-   Sensor/module error
-   Browser tab backgrounded and restored
-   Narrow viewport, landscape mobile, tablet split-screen
-   Large text, 200% zoom, keyboard-only operation
-   Long device names and translated labels

Do not silently replace invalid values with zero. Preserve the
distinction between a true measurement of zero and missing/invalid data.

## 12. Suggested CSS tokens

``` css
:root {
  color-scheme: light;

  --page: #f3f5f6;
  --surface: #ffffff;
  --text: #172235;
  --text-secondary: #586579;
  --text-muted: #778294;
  --border: #d8dee5;

  --accent: #008f72;
  --accent-soft: #e2f4ef;
  --ecg: #e52b2b;
  --warning: #a86400;
  --danger: #b42318;
  --focus: #245ddb;

  --radius-card: 8px;
  --radius-control: 7px;

  --space-1: 4px;
  --space-2: 8px;
  --space-3: 12px;
  --space-4: 16px;
  --space-5: 20px;
  --space-6: 24px;
  --space-8: 32px;
  --space-10: 40px;

  --content-max: 1440px;
  --page-gutter: 32px;
}

* {
  box-sizing: border-box;
}

.dashboard {
  width: min(100% - (2 * var(--page-gutter)), var(--content-max));
  margin-inline: auto;
}

.vitals-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: var(--space-4);
}

.monitor-grid {
  display: grid;
  grid-template-columns: minmax(0, 2.7fr) minmax(260px, 1fr);
  gap: var(--space-4);
  align-items: stretch;
}

@media (max-width: 1023px) {
  :root {
    --page-gutter: 24px;
  }

  .vitals-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .monitor-grid {
    grid-template-columns: minmax(0, 1fr);
  }
}

@media (max-width: 599px) {
  :root {
    --page-gutter: 16px;
  }

  .vitals-grid {
    grid-template-columns: minmax(0, 1fr);
  }

  .monitor-grid {
    gap: var(--space-4);
  }
}

@media (prefers-reduced-motion: reduce) {
  *,
  *::before,
  *::after {
    scroll-behavior: auto !important;
    animation-duration: 0.01ms !important;
    animation-iteration-count: 1 !important;
    transition-duration: 0.01ms !important;
  }
}
```

Treat this CSS as a starting point. Confirm breakpoints against actual
component content, not device names. If the project uses Tailwind or
another styling system, translate the tokens and behavior into that
system instead of introducing a second styling approach.

## 13. Component boundaries

Keep components small and aligned with meaningful responsibilities:

-   `DashboardHeader` --- product name, device state, last update
-   `VitalMetric` --- label, value, unit, freshness, configured state
-   `VitalsGrid` --- responsive arrangement only
-   `EcgPanel` --- plot, axes, time window, signal quality, supported
    controls
-   `SensorStatusList` --- module names and connection states
-   `ConnectionState` --- consistent text and indicator treatment
-   `EmptyState` / `ErrorState` --- waiting, stale, disconnected, and
    failed states

Keep hardware parsing, validation, connection management, and
clinical/configured thresholds outside presentation components. The UI
should receive typed, validated readings and explicit status fields
rather than infer hardware state from whether a value happens to be
present.

Suggested conceptual reading shape:

``` ts
type Reading<T> = {
  value: T | null;
  unit: string;
  receivedAt: string | null;
  status: "fresh" | "stale" | "unavailable" | "invalid";
};

type SensorState = {
  id: string;
  label: string;
  connection: "connected" | "reconnecting" | "disconnected" | "error";
  lastReceivedAt: string | null;
  message?: string;
};
```

This is an illustrative contract, not a requirement to adopt TypeScript
if the project uses another stack. Keep units explicit at the
hardware/data boundary and validate incoming values before rendering.

## 14. Avoiding generic "AI-generated" UI

Use these as hard review rules:

-   Do not add a gradient because a section looks empty.
-   Do not add a glass card, glow, or blurred background.
-   Do not add decorative charts, fake trends, random percentages,
    invented timestamps, or placeholder patient details to make the
    screen feel populated.
-   Do not use a generic "Welcome back" dashboard greeting.
-   Do not put every item inside a card; use whitespace, alignment, and
    dividers.
-   Do not use a different accent color for every metric.
-   Do not use pills for every piece of metadata.
-   Do not animate numbers, pulse dots continuously, or animate the ECG
    when no samples arrive.
-   Do not use oversized headings that push real readings below the
    fold.
-   Do not add labels such as "Excellent", "Optimal", or "Healthy"
    without validated meaning.
-   Do not overuse bold typography, uppercase labels, or tiny
    low-contrast metadata.
-   Do not use emoji.
-   Do not invent product functionality. Every control must map to a
    real capability.
-   Preserve this design language when adding features; do not redesign
    the whole interface for each new screen.

The goal is not to make the dashboard look "minimal" by removing useful
information. It is to make every visible element explain a reading, a
state, or an available action.

## 15. Implementation and review checklist

### Before implementation

-   [ ] Confirm which hardware modules exist and what connection
    telemetry each exposes.
-   [ ] Confirm sample rate, units, calibration, freshness timeout, and
    ECG time window.
-   [ ] Define configured thresholds and their source; do not invent
    clinical ranges.
-   [ ] Define loading, stale, disconnected, invalid, and error
    behavior.
-   [ ] Reuse the project's existing components and styling conventions
    where possible.

### Responsive review

-   [ ] Test at 320, 375, 430, 768, 1024, 1280, and 1440+ CSS pixels.
-   [ ] Test portrait and landscape on mobile/tablet.
-   [ ] Confirm no horizontal page scrolling.
-   [ ] Confirm values, units, and labels never overlap or clip.
-   [ ] Confirm the ECG remains legible and is not compressed into a
    narrow column.
-   [ ] Confirm the header and status remain readable when they wrap.
-   [ ] Test browser zoom to 200%.

### Functional review

-   [ ] Verify readings originate from hardware data, not hard-coded
    mock values in production.
-   [ ] Verify last-update time changes only when valid data is
    received.
-   [ ] Verify disconnecting one module updates only its state and
    dependent readings.
-   [ ] Verify a stopped ECG stream stops being labelled live.
-   [ ] Verify missing samples are not bridged as if they were real.
-   [ ] Verify reconnect, error, and stale states are distinct.
-   [ ] Verify controls perform the action their labels promise.

### Visual and accessibility review

-   [ ] Check contrast with an automated tool and manual review.
-   [ ] Navigate using keyboard only.
-   [ ] Verify screen-reader labels for metrics, status, and chart
    controls.
-   [ ] Verify color is not the only state indicator.
-   [ ] Verify reduced-motion preferences.
-   [ ] Remove decorative effects and elements that do not support
    monitoring.
-   [ ] Check console warnings, layout shifts, and chart rendering
    performance.

## 16. Impeccable-inspired design workflow

Use the linked Impeccable guide as a quality process, not as a prompt to
blindly apply a visual trend. Its core direction is to respect the
existing system, clarify hierarchy, remove unnecessary elements, adapt
layouts to real usage, and audit the finished interface.

Suggested review sequence: 1. **Distill:** list the essential readings
and states; remove anything that does not help someone monitor them. 2.
**Typeset:** establish clear hierarchy for the page title, metric value,
label, unit, and metadata. 3. **Layout:** verify the mobile-first order,
responsive breakpoints, and ECG width. 4. **Colorize:** apply the small
semantic palette; ensure status colors have consistent meanings. 5.
**Polish:** refine alignment, spacing, borders, focus states, and chart
labels without adding decoration. 6. **Harden:** test sensor failure,
stale data, narrow screens, keyboard use, zoom, and reduced motion. 7.
**Audit:** inspect the rendered interface at each breakpoint and remove
generic patterns that do not serve this product.

Reference: https://impeccable.style/

## Final rule

When there is a trade-off, prioritize **truthful sensor state, readable
measurements, waveform integrity, and responsive access** over visual
novelty. The dashboard should feel like a well-made instrument: quiet,
precise, and dependable.
