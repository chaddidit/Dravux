# Manual Verification Checks

Use the checks applicable to the declared scope. Record tester, environment, state, result, evidence, and limitations.

## Interaction and keyboard

- Reach every interactive control using expected keyboard commands.
- Confirm focus visibility, order, placement after state changes, and escape from components.
- Confirm no keyboard trap and no reliance on pointer-only or path-based gestures.
- Verify target size/spacing on actual devices or reliable rendered dimensions.

## Screen readers and accessible names

- Test at least the agreed browser/AT combinations.
- Confirm names, roles, values, states, instructions, errors, and dynamic announcements.
- Confirm reading/navigation order matches meaning.
- Confirm custom controls remain understandable and operable.

## Visual, zoom, reflow, and motion

- Verify contrast across real component states and backgrounds.
- Confirm color is not the only signal.
- Test text resize, browser zoom, reflow, orientation, and small viewports.
- Respect reduced-motion and verify no harmful flashing or unexpected movement.

## Content and cognition

- Judge whether alt text, captions, transcripts, labels, instructions, and errors serve the content purpose.
- Check clarity, consistency, predictability, recovery, sensory load, and avoidable cognitive effort.
- Verify localization expansion and translated meaning, not only container size.

## Documents and visual evidence

- For PDFs, verify tags, headings, reading order, lists, tables, links, language, forms, and AT navigation.
- For screenshots, treat absent programmatic evidence as unknown.
- For SVG/diagrams, verify an equivalent text path for meaningful information.

## Design intent

- Verify focus order, component states, target sizes, semantics, labels, errors, motion, and localization annotations.
- Compare the implemented product with the documented design intent; a design-tool finding is not proof of production behavior.

## User involvement

When the product risk and scope warrant it, include disabled users in research/usability testing. Synthetic personas and AI-generated feedback do not replace real people.

## Completion rule

Do not mark a manual check complete because it is inconvenient, unavailable, or out of time. Record it as pending. A completed manual check requires the preflight to declare manual-evidence capability and the report to include `MANUAL_OBSERVATION` evidence. Pending checks block `VERIFIED PASS`; they do not erase an independently established `VERIFIED FAIL` supported by reproducible normative evidence.
