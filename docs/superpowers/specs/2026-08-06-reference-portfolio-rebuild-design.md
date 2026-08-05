# Reference Portfolio Rebuild Design

## Goal

Replace the deployed portfolio landing page with a faithful desktop recreation of the approved reference image. The page remains a public recruiter portfolio and preserves the existing verified login, personal DeepSeek key management, and chat flows.

## Visual Contract

The 1536px desktop reference is the acceptance target:

- Warm off-white page surface, 1px cool-gray borders, navy typography, and restrained cornflower-blue accents.
- A 60px top navigation bar with the wordmark at left and five anchor links at right: 首页, 项目, 技术栈, 经历, 关于.
- A 328px two-column hero. The left column contains the Chinese name, role, summary, and GitHub button. The right column is an original, pale ink-wash mountain landscape with a pavilion and birds, matched to the reference composition without copying its source artwork.
- A single three-column capability row directly beneath the hero. Each card has a large muted-blue line icon, title, description, and four compact technology tags.
- A three-column content grid below: experience timeline at left, selected-project list in the center, and a dark navy AI assistant panel at right.
- The assistant panel reproduces the visual chat bubbles and explanation in the reference. Its API-key CTA opens the existing authentication flow; it must not pretend to be a live conversation before the user signs in.
- The page must not expose the user's phone number or email address. GitHub remains the only public contact destination.

## Content Contract

- Public copy uses the user's confirmed project descriptions: cross-border bank statement verification Agent, 易商宝 merchant registration Agent, and Derm AI consultation.
- Experience and project entries use the approved resume-derived content already in the portfolio branch. Avoid unsupported performance claims and private client data.
- Existing auth, email verification, API-key storage, and chat API routes are unchanged.

## Interaction And Responsive Behavior

- Navigation anchors scroll to the matching sections. The GitHub button opens `https://github.com/dqyydq` in a new tab.
- The assistant CTA opens the existing login screen. Authenticated chat remains a separate application state.
- At widths below 900px: navigation wraps into a compact row, hero becomes vertical, the capability row and content grid stack, and all text stays readable. The desktop target remains the primary visual acceptance criterion.

## Implementation Boundaries

- Rebuild only the public portfolio portion of `frontend/src/App.tsx` and its page styles/assets. Do not change the backend deployment, API schemas, authentication behavior, or database schema.
- Use an original generated raster landscape for the hero and established icon components for UI icons.
- Validate with a production frontend build. Run a visual comparison at the desktop reference viewport before publishing.

## Acceptance Checks

1. The deployed public page uses the reference's section order and three-column lower layout, not the old split hero layout.
2. At a 1536px viewport, navigation, hero height, card row, and lower-column proportions visually align with the reference.
3. GitHub, navigation anchors, and the assistant entry work.
4. `npm run build` succeeds and the existing auth/chat paths still compile.
