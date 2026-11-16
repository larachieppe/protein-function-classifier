# Basil & Ember: table QR menu app

A React Native (Expo) app that makes the restaurant QR code experience smooth. Guests scan the code on their table, browse a fast scrolling menu and order from their seat.

## What it does

- **Scan to start:** the camera reads the table's QR code and opens the menu for that table. Guests can also type the table number or open a demo menu.
- **Scrolling menu with sticky tabs:** the category tabs stay pinned and highlight the section you're scrolling through. Tap a tab to jump to it.
- **Search and dietary filters:** search by dish or ingredient, and filter for vegetarian, vegan, gluten-free, dairy-free or spicy.
- **Dish details:** each dish shows its allergens and who it suits, plus required choices (pizza size, steak cooking), a note for the kitchen and a quantity.
- **Order tray:** a bottom bar shows the item count and total, and you can review, remove and send the order to the kitchen. The order is saved per table, so it survives the app closing.
- **Call server / Request bill:** one tap each, with a confirmation on screen.
- Light and dark mode, haptic feedback and screen-reader labels.

> **Demo only:** nothing is sent anywhere yet. "Send to kitchen", "Call server" and "Request bill" only show a confirmation. A backend is the next step.

## Run it on your phone

1. Install **Expo Go** from the App Store or Google Play.
2. On your computer, in this folder, install dependencies:

   ```bash
   npm install
   ```

3. Start the dev server:

   ```bash
   npx expo start
   ```

4. Scan the QR code it prints. On iPhone, use the Camera app; on Android, use the scanner inside Expo Go.

To test the in-app scanner, open one of the images in `test-qr/` on another screen or print it, and scan it from the app's first screen.

## Table QR codes

The app reads the table number from any of these formats, so existing restaurant codes usually work:

| Code contains | Table |
|---|---|
| `basilember://table/12` | 12 |
| `https://your-site.example/menu?table=12` | 12 |
| `https://your-site.example/t/12` | 12 |
| `T12` or `12` | 12 |

The parsing lives in `parseTable` in `src/data/menu.ts`.

## Project layout

```
App.tsx                      scan screen → menu screen for that table
src/data/menu.ts             restaurant info, menu, options, QR parsing
src/state/order.tsx          order for the table, saved on the phone
src/screens/ScanScreen.tsx   QR scanner + manual table entry
src/screens/MenuScreen.tsx   sticky tabs, search, filters, dish list, order bar
src/components/              bottom sheets for dishes and the order, placeholder plate art
src/theme.ts                 light and dark colours
```

## Next steps

- **Backend:** send orders to a kitchen screen, and alert servers when a table calls or asks for the bill.
- **Staff tools:** edit the menu and mark dishes sold out live.
- **Real dish photos:** swap `<Plate>` for `<Image>`.
- **Pay at the table and split the bill.**
- **Publish:** build with EAS (`npx eas-cli@latest build`) for the App Store and Play Store.
