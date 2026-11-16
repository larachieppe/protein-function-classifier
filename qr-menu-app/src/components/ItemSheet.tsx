import * as Haptics from 'expo-haptics';
import { useState } from 'react';
import { Pressable, StyleSheet, Text, TextInput, View } from 'react-native';
import { COOK, DIETS, MenuItem, money, Option, SIZES } from '../data/menu';
import { useOrder } from '../state/order';
import { Theme, useTheme } from '../theme';
import { Plate } from './Plate';
import { Sheet } from './Sheet';

type Props = { item: MenuItem | null; onClose: () => void; onAdded: (msg: string) => void };

export function ItemSheet({ item, onClose, onAdded }: Props) {
  // Keyed on the dish so size, cooking, note and quantity reset each time a dish opens.
  return item ? <DishSheet key={item.id} item={item} onClose={onClose} onAdded={onAdded} /> : <Sheet visible={false} onClose={onClose}>{null}</Sheet>;
}

function DishSheet({ item, onClose, onAdded }: { item: MenuItem; onClose: () => void; onAdded: (msg: string) => void }) {
  const t = useTheme();
  const s = styles(t);
  const { add } = useOrder();
  const [size, setSize] = useState(0);
  const [cook, setCook] = useState(1);
  const [note, setNote] = useState('');
  const [qty, setQty] = useState(1);

  const unit = item.price + (item.sizes ? SIZES[size].extra : 0);
  const suitable = [...item.diet.filter((d) => d !== 'sp').map((d) => DIETS[d]), ...(item.diet.includes('sp') ? ['Spicy'] : [])];

  const addToOrder = () => {
    const options = [...(item.sizes ? [SIZES[size].label] : []), ...(item.cook ? [COOK[cook].label] : [])];
    add({ itemId: item.id, options, note: note.trim(), unitPrice: unit, qty });
    Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success).catch(() => {});
    onClose();
    onAdded(`Added ${qty} × ${item.name}`);
  };

  const footer = (
    <View style={s.row}>
      <View style={s.stepper}>
        <Pressable style={s.stepBtn} onPress={() => setQty((q) => Math.max(1, q - 1))} accessibilityLabel="Fewer" hitSlop={6}>
          <Text style={s.stepTxt}>−</Text>
        </Pressable>
        <Text style={s.qty}>{qty}</Text>
        <Pressable style={s.stepBtn} onPress={() => setQty((q) => Math.min(20, q + 1))} accessibilityLabel="More" hitSlop={6}>
          <Text style={s.stepTxt}>+</Text>
        </Pressable>
      </View>
      <Pressable
        style={({ pressed }) => [s.primary, item.soldOut && { opacity: 0.5 }, pressed && { opacity: 0.85 }]}
        disabled={item.soldOut}
        onPress={addToOrder}
      >
        <Text style={s.primaryTxt}>{item.soldOut ? 'Sold out tonight' : 'Add to order'}</Text>
        {!item.soldOut ? <Text style={[s.primaryTxt, s.num]}>{money(unit * qty)}</Text> : null}
      </Pressable>
    </View>
  );

  return (
    <Sheet visible onClose={onClose} footer={footer}>
      <View style={{ gap: 12 }}>
        <Plate hue={item.hue} size="100%" radius={18} style={{ aspectRatio: 1.9 }} />
        <View style={{ gap: 4 }}>
          <Text style={s.title}>{item.name}</Text>
          <Text style={s.desc}>{item.desc}</Text>
        </View>
        <View style={s.allergens}>
          <Text style={s.small}>
            <Text style={s.bold}>Contains: </Text>
            {item.allergens.length ? item.allergens.join(', ') : 'No major allergens'}
          </Text>
          {suitable.length ? (
            <Text style={s.small}>
              <Text style={s.bold}>Suitable for: </Text>
              {suitable.join(' · ')}
            </Text>
          ) : null}
        </View>
        {item.sizes ? <Choice t={t} title="Size" options={SIZES} value={size} onChange={setSize} /> : null}
        {item.cook ? <Choice t={t} title="How would you like it cooked?" options={COOK} value={cook} onChange={setCook} /> : null}
        <TextInput
          style={s.note}
          placeholder="Note for the kitchen (e.g. no onion)"
          placeholderTextColor={t.muted}
          value={note}
          onChangeText={setNote}
          multiline
          maxLength={140}
        />
      </View>
    </Sheet>
  );
}

function Choice({ t, title, options, value, onChange }: { t: Theme; title: string; options: Option[]; value: number; onChange: (v: number) => void }) {
  const s = styles(t);
  return (
    <View style={{ gap: 8 }} accessibilityRole="radiogroup">
      <View style={s.optHead}>
        <Text style={s.bold}>{title}</Text>
        <Text style={s.small}>Required</Text>
      </View>
      {options.map((o, i) => {
        const on = i === value;
        return (
          <Pressable
            key={o.label}
            onPress={() => {
              Haptics.selectionAsync().catch(() => {});
              onChange(i);
            }}
            style={[s.opt, on && { borderColor: t.basil, backgroundColor: t.basilSoft }]}
            accessibilityRole="radio"
            accessibilityState={{ checked: on }}
          >
            <View style={[s.radio, on && { borderColor: t.basil }]}>{on ? <View style={[s.radioDot, { backgroundColor: t.basil }]} /> : null}</View>
            <Text style={s.optTxt}>{o.label}</Text>
            <Text style={s.small}>{o.extra ? `+${money(o.extra)}` : ''}</Text>
          </Pressable>
        );
      })}
    </View>
  );
}

const styles = (t: Theme) =>
  StyleSheet.create({
    title: { fontSize: 24, fontWeight: '800', color: t.ink, letterSpacing: -0.3 },
    desc: { fontSize: 15, color: t.muted, lineHeight: 21 },
    allergens: { backgroundColor: t.bg, borderRadius: 12, padding: 12, gap: 4 },
    small: { fontSize: 13, color: t.muted },
    bold: { fontWeight: '600', color: t.ink, fontSize: 14 },
    optHead: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'baseline' },
    opt: { flexDirection: 'row', alignItems: 'center', gap: 12, borderWidth: 1, borderColor: t.line, borderRadius: 12, paddingHorizontal: 14, paddingVertical: 12 },
    optTxt: { flex: 1, fontSize: 15, color: t.ink },
    radio: { width: 20, height: 20, borderRadius: 10, borderWidth: 2, borderColor: t.muted, alignItems: 'center', justifyContent: 'center' },
    radioDot: { width: 10, height: 10, borderRadius: 5 },
    note: { borderWidth: 1, borderColor: t.line, borderRadius: 12, padding: 12, minHeight: 56, fontSize: 15, color: t.ink, backgroundColor: t.bg, textAlignVertical: 'top' },
    row: { flexDirection: 'row', gap: 10, alignItems: 'center' },
    stepper: { flexDirection: 'row', alignItems: 'center', borderWidth: 1, borderColor: t.line, borderRadius: 14, height: 52 },
    stepBtn: { width: 44, height: 52, alignItems: 'center', justifyContent: 'center' },
    stepTxt: { fontSize: 22, color: t.ink },
    qty: { minWidth: 22, textAlign: 'center', fontSize: 16, fontWeight: '600', color: t.ink, fontVariant: ['tabular-nums'] },
    primary: { flex: 1, height: 52, borderRadius: 14, backgroundColor: t.basil, flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingHorizontal: 18 },
    primaryTxt: { color: t.onBasil, fontWeight: '700', fontSize: 15 },
    num: { fontVariant: ['tabular-nums'] },
  });
