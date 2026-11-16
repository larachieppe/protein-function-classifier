import { Pressable, StyleSheet, Text, View } from 'react-native';
import { ITEMS_BY_ID, money } from '../data/menu';
import { useOrder } from '../state/order';
import { Theme, useTheme } from '../theme';
import { Sheet } from './Sheet';

export function OrderSheet({ visible, table, onClose, onSend }: { visible: boolean; table: string; onClose: () => void; onSend: () => void }) {
  const t = useTheme();
  const s = styles(t);
  const { lines, total, remove } = useOrder();

  const footer = (
    <View style={s.row}>
      <Pressable style={s.ghost} onPress={onClose}>
        <Text style={s.ghostTxt}>Keep browsing</Text>
      </Pressable>
      <Pressable style={({ pressed }) => [s.primary, !lines.length && { opacity: 0.5 }, pressed && { opacity: 0.85 }]} disabled={!lines.length} onPress={onSend}>
        <Text style={s.primaryTxt}>Send to kitchen</Text>
      </Pressable>
    </View>
  );

  return (
    <Sheet visible={visible} onClose={onClose} footer={footer}>
      <Text style={s.title}>Your order · Table {table}</Text>
      {lines.length === 0 ? <Text style={s.empty}>Nothing here yet.</Text> : null}
      {lines.map((l, i) => {
        const item = ITEMS_BY_ID[l.itemId];
        return (
          <View key={l.key} style={[s.line, i > 0 && { borderTopWidth: StyleSheet.hairlineWidth, borderTopColor: t.line }]}>
            <Text style={s.q}>{l.qty}×</Text>
            <View style={{ flex: 1, gap: 2 }}>
              <Text style={s.name}>{item.name}</Text>
              {l.options.length ? <Text style={s.small}>{l.options.join(' · ')}</Text> : null}
              {l.note ? <Text style={s.small}>“{l.note}”</Text> : null}
              <Pressable onPress={() => remove(l.key)} hitSlop={8} accessibilityLabel={`Remove ${item.name}`}>
                <Text style={s.remove}>Remove</Text>
              </Pressable>
            </View>
            <Text style={s.price}>{money(l.unitPrice * l.qty)}</Text>
          </View>
        );
      })}
      <View style={s.total}>
        <Text style={s.totalTxt}>Total</Text>
        <Text style={[s.totalTxt, s.num]}>{money(total)}</Text>
      </View>
      <Text style={s.small}>Prices include tax. Your server can split the bill at the end.</Text>
    </Sheet>
  );
}

const styles = (t: Theme) =>
  StyleSheet.create({
    title: { fontSize: 22, fontWeight: '800', color: t.ink, marginBottom: 8 },
    empty: { color: t.muted, paddingVertical: 24, textAlign: 'center' },
    line: { flexDirection: 'row', gap: 12, paddingVertical: 12, alignItems: 'flex-start' },
    q: { fontWeight: '700', color: t.basil, fontVariant: ['tabular-nums'], fontSize: 15 },
    name: { fontSize: 15, fontWeight: '600', color: t.ink },
    small: { fontSize: 13, color: t.muted },
    remove: { fontSize: 13, color: t.muted, textDecorationLine: 'underline', marginTop: 4 },
    price: { fontSize: 15, fontWeight: '600', color: t.ink, fontVariant: ['tabular-nums'] },
    total: { flexDirection: 'row', justifyContent: 'space-between', borderTopWidth: 2, borderTopColor: t.ink, paddingTop: 10, marginTop: 6, marginBottom: 8 },
    totalTxt: { fontSize: 17, fontWeight: '700', color: t.ink },
    num: { fontVariant: ['tabular-nums'] },
    row: { flexDirection: 'row', gap: 10 },
    ghost: { flex: 1, height: 52, borderRadius: 14, borderWidth: 1, borderColor: t.line, alignItems: 'center', justifyContent: 'center' },
    ghostTxt: { fontWeight: '600', color: t.ink, fontSize: 15 },
    primary: { flex: 1.3, height: 52, borderRadius: 14, backgroundColor: t.basil, alignItems: 'center', justifyContent: 'center' },
    primaryTxt: { color: t.onBasil, fontWeight: '700', fontSize: 15 },
  });
