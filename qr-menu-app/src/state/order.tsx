import AsyncStorage from '@react-native-async-storage/async-storage';
import { createContext, ReactNode, useContext, useEffect, useMemo, useState } from 'react';
import { ITEMS_BY_ID } from '../data/menu';

export type OrderLine = {
  key: string;
  itemId: string;
  options: string[];
  note: string;
  unitPrice: number;
  qty: number;
};

type OrderState = {
  lines: OrderLine[];
  count: number;
  total: number;
  qtyOf: (itemId: string) => number;
  add: (line: Omit<OrderLine, 'key'>) => void;
  remove: (key: string) => void;
  clear: () => void;
};

const Ctx = createContext<OrderState | null>(null);

/** Keeps the table's order on the phone so it survives the app being closed. */
export function OrderProvider({ table, children }: { table: string; children: ReactNode }) {
  const storageKey = `order:table:${table}`;
  const [lines, setLines] = useState<OrderLine[]>([]);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    let alive = true;
    AsyncStorage.getItem(storageKey)
      .then((raw) => {
        if (!alive || !raw) return;
        const saved: OrderLine[] = JSON.parse(raw);
        setLines(saved.filter((l) => ITEMS_BY_ID[l.itemId]));
      })
      .catch(() => {})
      .finally(() => alive && setLoaded(true));
    return () => {
      alive = false;
    };
  }, [storageKey]);

  useEffect(() => {
    if (loaded) AsyncStorage.setItem(storageKey, JSON.stringify(lines)).catch(() => {});
  }, [lines, loaded, storageKey]);

  const value = useMemo<OrderState>(
    () => ({
      lines,
      count: lines.reduce((a, l) => a + l.qty, 0),
      total: lines.reduce((a, l) => a + l.qty * l.unitPrice, 0),
      qtyOf: (id) => lines.filter((l) => l.itemId === id).reduce((a, l) => a + l.qty, 0),
      add: (line) => {
        const key = `${line.itemId}|${line.options.join(',')}|${line.note}`;
        setLines((prev) => {
          const existing = prev.find((l) => l.key === key);
          if (existing) return prev.map((l) => (l.key === key ? { ...l, qty: l.qty + line.qty } : l));
          return [...prev, { ...line, key }];
        });
      },
      remove: (key) => setLines((prev) => prev.filter((l) => l.key !== key)),
      clear: () => setLines([]),
    }),
    [lines],
  );

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useOrder() {
  const v = useContext(Ctx);
  if (!v) throw new Error('useOrder must be used inside OrderProvider');
  return v;
}
