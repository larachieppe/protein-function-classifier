export type Diet = 'v' | 'vg' | 'gf' | 'df' | 'sp';

export const DIETS: Record<Diet, string> = {
  v: 'Vegetarian',
  vg: 'Vegan',
  gf: 'Gluten-free',
  df: 'Dairy-free',
  sp: 'Spicy',
};

export type Option = { label: string; extra: number };

export type MenuItem = {
  id: string;
  name: string;
  desc: string;
  price: number;
  /** Hue (0–360) for the placeholder plate artwork. Swap for real photos later. */
  hue: number;
  diet: Diet[];
  allergens: string[];
  popular?: boolean;
  soldOut?: boolean;
  sizes?: boolean;
  cook?: boolean;
};

export type Category = { id: string; name: string; sub?: string; items: MenuItem[] };

export const RESTAURANT = {
  name: 'Basil & Ember',
  tagline: 'Wood-fired kitchen · Open until 22:30',
};

export const SIZES: Option[] = [
  { label: 'Regular 11"', extra: 0 },
  { label: 'Large 14"', extra: 5 },
];

export const COOK: Option[] = [
  { label: 'Rare', extra: 0 },
  { label: 'Medium rare', extra: 0 },
  { label: 'Medium', extra: 0 },
  { label: 'Well done', extra: 0 },
];

export const MENU: Category[] = [
  {
    id: 'small',
    name: 'Small plates',
    sub: 'Good for sharing. Most tables order 2–3.',
    items: [
      { id: 'burrata', name: 'Burrata & charred peach', desc: 'Creamy burrata, wood-roasted peaches, basil oil, toasted pistachio.', price: 14, hue: 38, diet: ['v', 'gf'], allergens: ['Dairy', 'Tree nuts'], popular: true },
      { id: 'croq', name: 'Smoked ham croquetas', desc: 'Four crisp croquetas with aioli and pickled shallot.', price: 11, hue: 30, diet: [], allergens: ['Gluten', 'Dairy', 'Egg'] },
      { id: 'pad', name: 'Blistered padróns', desc: 'Flaked salt, lemon, smoked paprika.', price: 9, hue: 110, diet: ['vg', 'gf', 'df'], allergens: [] },
      { id: 'calam', name: 'Ember-grilled squid', desc: 'Chili, garlic, parsley, grilled lemon.', price: 15, hue: 20, diet: ['gf', 'df', 'sp'], allergens: ['Molluscs'] },
    ],
  },
  {
    id: 'pizza',
    name: 'Pizza',
    sub: '48-hour dough, baked at 450°C. Gluten-free base available.',
    items: [
      { id: 'marg', name: 'Margherita', desc: 'San Marzano tomato, fior di latte, basil.', price: 16, hue: 5, diet: ['v'], allergens: ['Gluten', 'Dairy'], popular: true, sizes: true },
      { id: 'diav', name: 'Diavola', desc: 'Spicy salami, Calabrian chili honey, mozzarella.', price: 19, hue: 8, diet: ['sp'], allergens: ['Gluten', 'Dairy'], sizes: true },
      { id: 'funghi', name: 'Wild mushroom & truffle', desc: 'Roasted mushrooms, taleggio, thyme, truffle oil.', price: 21, hue: 35, diet: ['v'], allergens: ['Gluten', 'Dairy'], sizes: true },
      { id: 'verde', name: 'Verde', desc: 'Basil pesto, courgette, cashew ricotta, chili flakes.', price: 18, hue: 100, diet: ['vg', 'df'], allergens: ['Gluten', 'Tree nuts'], sizes: true, soldOut: true },
    ],
  },
  {
    id: 'mains',
    name: 'Mains',
    sub: 'From the grill and the pasta bench.',
    items: [
      { id: 'rigatoni', name: 'Rigatoni alla vodka', desc: 'Tomato, cream, chili, parmesan.', price: 22, hue: 12, diet: ['v'], allergens: ['Gluten', 'Dairy'], popular: true },
      { id: 'steak', name: 'Flat-iron steak', desc: '250g grass-fed, salsa verde, ember potatoes.', price: 34, hue: 15, diet: ['gf'], allergens: ['Dairy'], cook: true },
      { id: 'bass', name: 'Whole sea bass', desc: 'Grilled over oak, fennel salad, brown butter capers.', price: 31, hue: 200, diet: ['gf'], allergens: ['Fish', 'Dairy'] },
      { id: 'cauli', name: 'Charred cauliflower', desc: 'Tahini, pomegranate, dukkah, herbs.', price: 20, hue: 45, diet: ['vg', 'gf', 'df'], allergens: ['Sesame', 'Tree nuts'] },
    ],
  },
  {
    id: 'sides',
    name: 'Sides',
    items: [
      { id: 'fries', name: 'Rosemary fries', desc: 'Parmesan, rosemary salt, aioli.', price: 7, hue: 48, diet: ['v'], allergens: ['Dairy', 'Egg'] },
      { id: 'greens', name: 'Garden greens', desc: 'House vinaigrette, shaved fennel.', price: 8, hue: 95, diet: ['vg', 'gf', 'df'], allergens: ['Mustard'] },
    ],
  },
  {
    id: 'dessert',
    name: 'Desserts',
    items: [
      { id: 'tira', name: 'Tiramisu', desc: 'Espresso-soaked savoiardi, mascarpone, cocoa.', price: 11, hue: 28, diet: ['v'], allergens: ['Gluten', 'Dairy', 'Egg'], popular: true },
      { id: 'affo', name: 'Affogato', desc: 'Fior di latte gelato drowned in espresso.', price: 8, hue: 25, diet: ['v', 'gf'], allergens: ['Dairy'] },
    ],
  },
  {
    id: 'drinks',
    name: 'Drinks',
    sub: "Ask your server about today's wines by the glass.",
    items: [
      { id: 'spritz', name: 'Blood orange spritz', desc: 'Aperitivo, prosecco, soda, orange.', price: 13, hue: 15, diet: ['vg', 'gf', 'df'], allergens: ['Sulphites'] },
      { id: 'lemon', name: 'House lemonade', desc: 'Basil, lemon, sparkling water. Alcohol-free.', price: 6, hue: 60, diet: ['vg', 'gf', 'df'], allergens: [] },
      { id: 'negroni', name: 'Smoked negroni', desc: 'Gin, Campari, vermouth, oak smoke.', price: 15, hue: 5, diet: ['vg', 'gf', 'df'], allergens: ['Sulphites'] },
    ],
  },
];

export const ITEMS_BY_ID: Record<string, MenuItem> = Object.fromEntries(
  MENU.flatMap((c) => c.items).map((i) => [i.id, i]),
);

export const money = (n: number) => `$${n.toFixed(2)}`;

/**
 * Reads a table number out of whatever the table's QR code holds, e.g.
 * "https://basilember.example/menu?table=12", "basilember://table/12", "T12" or "12".
 */
export function parseTable(data: string): string | null {
  const s = data.trim();
  const m =
    s.match(/[?&]table=(\d{1,3})\b/i) ||
    s.match(/\/(?:table|t)\/(\d{1,3})\b/i) ||
    s.match(/^(?:table\s*|t)?(\d{1,3})$/i);
  return m ? String(Number(m[1])) : null;
}
