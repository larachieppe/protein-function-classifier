import * as Haptics from 'expo-haptics';
import { useEffect, useMemo, useRef, useState } from 'react';
import {
  Animated,
  LayoutChangeEvent,
  NativeScrollEvent,
  NativeSyntheticEvent,
  Pressable,
  ScrollView,
  ScrollViewInstance,
  StyleSheet,
  Text,
  TextInput,
  View,
} from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { ItemSheet } from '../components/ItemSheet';
import { OrderSheet } from '../components/OrderSheet';
import { Plate } from '../components/Plate';
import { Diet, DIETS, MENU, MenuItem, money, RESTAURANT } from '../data/menu';
import { useOrder } from '../state/order';
import { Theme, useTheme } from '../theme';

export function MenuScreen({ table, onChangeTable }: { table: string; onChangeTable: () => void }) {
  const t = useTheme();
  const s = useMemo(() => styles(t), [t]);
  const insets = useSafeAreaInsets();
  const order = useOrder();

  const [query, setQuery] = useState('');
  const [filters, setFilters] = useState<Set<Diet>>(new Set());
  const [activeCat, setActiveCat] = useState(MENU[0].id);
  const [openItem, setOpenItem] = useState<MenuItem | null>(null);
  const [orderOpen, setOrderOpen] = useState(false);
  const [status, setStatus] = useState<string | null>(null);

  const scrollRef = useRef<ScrollViewInstance>(null);
  const chipsRef = useRef<ScrollViewInstance>(null);
  const sectionY = useRef<Record<string, number>>({});
  const chipX = useRef<Record<string, { x: number; w: number }>>({});
  const railH = useRef(0);
  const chipsW = useRef(0);
  const jumpingUntil = useRef(0);

  // Search and dietary filters narrow every section; empty sections drop out of the menu and the tabs.
  const sections = useMemo(() => {
    const q = query.trim().toLowerCase();
    return MENU.map((c) => ({
      ...c,
      items: c.items.filter(
        (i) => [...filters].every((f) => i.diet.includes(f)) && (!q || `${i.name} ${i.desc}`.toLowerCase().includes(q)),
      ),
    })).filter((c) => c.items.length);
  }, [query, filters]);

  // Keep the highlighted tab visible in the tab strip.
  useEffect(() => {
    const c = chipX.current[activeCat];
    if (c) chipsRef.current?.scrollTo({ x: Math.max(0, c.x - chipsW.current / 2 + c.w / 2), animated: true });
  }, [activeCat]);

  const onScroll = (e: NativeSyntheticEvent<NativeScrollEvent>) => {
    if (Date.now() < jumpingUntil.current) return;
    const y = e.nativeEvent.contentOffset.y + railH.current + 12;
    let current = sections[0]?.id;
    for (const c of sections) {
      const top = sectionY.current[c.id];
      if (top !== undefined && top <= y) current = c.id;
    }
    if (current && current !== activeCat) setActiveCat(current);
  };

  const jumpTo = (id: string) => {
    Haptics.selectionAsync().catch(() => {});
    setActiveCat(id);
    jumpingUntil.current = Date.now() + 600;
    const y = sectionY.current[id];
    if (y !== undefined) scrollRef.current?.scrollTo({ y: Math.max(0, y - railH.current), animated: true });
  };

  const toggleFilter = (d: Diet) =>
    setFilters((prev) => {
      const next = new Set(prev);
      next.has(d) ? next.delete(d) : next.add(d);
      return next;
    });

  // Toast
  const toastY = useRef(new Animated.Value(-120)).current;
  const [toastMsg, setToastMsg] = useState('');
  const toastTimer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);
  const toast = (msg: string) => {
    setToastMsg(msg);
    clearTimeout(toastTimer.current);
    Animated.spring(toastY, { toValue: 0, useNativeDriver: true, speed: 18 }).start();
    toastTimer.current = setTimeout(() => Animated.timing(toastY, { toValue: -120, duration: 220, useNativeDriver: true }).start(), 2200);
  };
  useEffect(() => () => clearTimeout(toastTimer.current), []);

  const callServer = () => {
    Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Medium).catch(() => {});
    setStatus(`A server is on the way to table ${table}.`);
    toast('Server called');
  };
  const requestBill = () => {
    Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Medium).catch(() => {});
    setStatus('Your bill is on its way. You can pay at the table by card or phone.');
    toast('Bill requested');
  };
  const sendOrder = () => {
    order.clear();
    setOrderOpen(false);
    Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success).catch(() => {});
    setStatus(`Order sent. The kitchen has it, and your server will bring it to table ${table}.`);
    toast('Order sent to the kitchen');
  };

  return (
    <View style={[s.root, { paddingTop: insets.top }]}>
      <ScrollView
        ref={scrollRef}
        stickyHeaderIndices={[1]}
        onScroll={onScroll}
        scrollEventThrottle={16}
        keyboardShouldPersistTaps="handled"
        keyboardDismissMode="on-drag"
        contentContainerStyle={{ paddingBottom: 120 + insets.bottom }}
      >
        {/* 0: header */}
        <View style={s.header}>
          <View style={s.brandRow}>
            <View style={{ flex: 1 }}>
              <Text style={s.brand}>{RESTAURANT.name}</Text>
              <Text style={s.muted}>{RESTAURANT.tagline}</Text>
            </View>
            <Pressable style={s.table} onPress={onChangeTable} accessibilityLabel={`Table ${table}. Tap to change table`}>
              <Text style={s.tableSmall}>TABLE</Text>
              <Text style={s.tableNum}>{table}</Text>
            </Pressable>
          </View>
          <View style={s.actions}>
            <Pressable style={({ pressed }) => [s.action, pressed && s.pressed]} onPress={callServer}>
              <Text style={s.actionTxt}>Call server</Text>
            </Pressable>
            <Pressable style={({ pressed }) => [s.action, pressed && s.pressed]} onPress={requestBill}>
              <Text style={s.actionTxt}>Request bill</Text>
            </Pressable>
          </View>
          {status ? (
            <Pressable style={s.status} onPress={() => setStatus(null)} accessibilityHint="Dismiss">
              <Text style={s.statusTxt}>{status}</Text>
            </Pressable>
          ) : null}
        </View>

        {/* 1: sticky rail */}
        <View style={s.rail} onLayout={(e: LayoutChangeEvent) => (railH.current = e.nativeEvent.layout.height)}>
          <TextInput
            style={s.search}
            value={query}
            onChangeText={setQuery}
            placeholder="Search dishes or ingredients"
            placeholderTextColor={t.muted}
            clearButtonMode="while-editing"
            returnKeyType="search"
          />
          <ScrollView
            ref={chipsRef}
            horizontal
            showsHorizontalScrollIndicator={false}
            contentContainerStyle={s.chips}
            onLayout={(e) => (chipsW.current = e.nativeEvent.layout.width)}
          >
            {sections.map((c) => {
              const on = c.id === activeCat;
              return (
                <Pressable
                  key={c.id}
                  onPress={() => jumpTo(c.id)}
                  onLayout={(e) => (chipX.current[c.id] = { x: e.nativeEvent.layout.x, w: e.nativeEvent.layout.width })}
                  style={[s.chip, on && s.chipOn]}
                  accessibilityRole="tab"
                  accessibilityState={{ selected: on }}
                >
                  <Text style={[s.chipTxt, on && s.chipTxtOn]}>{c.name}</Text>
                </Pressable>
              );
            })}
          </ScrollView>
          <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={s.filters}>
            {(Object.keys(DIETS) as Diet[]).map((d) => {
              const on = filters.has(d);
              return (
                <Pressable key={d} onPress={() => toggleFilter(d)} style={[s.ftag, on && s.ftagOn]} accessibilityRole="checkbox" accessibilityState={{ checked: on }}>
                  <Text style={[s.ftagTxt, on && { color: t.ink }]}>{DIETS[d]}</Text>
                </Pressable>
              );
            })}
          </ScrollView>
        </View>

        {/* sections */}
        {sections.map((c) => (
          <View key={c.id} style={s.section} onLayout={(e) => (sectionY.current[c.id] = e.nativeEvent.layout.y)}>
            <Text style={s.h2}>{c.name}</Text>
            {c.sub ? <Text style={[s.muted, { marginBottom: 6 }]}>{c.sub}</Text> : null}
            {c.items.map((i, idx) => {
              const qty = order.qtyOf(i.id);
              return (
                <Pressable
                  key={i.id}
                  onPress={() => setOpenItem(i)}
                  style={({ pressed }) => [s.item, idx > 0 && s.itemBorder, i.soldOut && { opacity: 0.5 }, pressed && s.pressed]}
                  accessibilityLabel={`${i.name}, ${money(i.price)}${i.soldOut ? ', sold out' : ''}`}
                >
                  <View style={{ flex: 1, gap: 4 }}>
                    <View style={s.nameRow}>
                      <Text style={s.itemName}>{i.name}</Text>
                      {i.popular ? <Text style={s.pop}>POPULAR</Text> : null}
                      {i.soldOut ? <Text style={s.out}>SOLD OUT</Text> : null}
                    </View>
                    <Text style={s.desc} numberOfLines={2}>
                      {i.desc}
                    </Text>
                    <View style={s.metaRow}>
                      <Text style={s.price}>{money(i.price)}</Text>
                      {i.diet.map((d) => (
                        <Text key={d} style={s.diet} accessibilityLabel={DIETS[d]}>
                          {d.toUpperCase()}
                        </Text>
                      ))}
                    </View>
                  </View>
                  <View>
                    <Plate hue={i.hue} size={88} />
                    {qty ? (
                      <View style={s.qtyBadge}>
                        <Text style={s.qtyTxt}>{qty}</Text>
                      </View>
                    ) : null}
                    {!i.soldOut ? (
                      <View style={s.addBtn}>
                        <Text style={s.addTxt}>+</Text>
                      </View>
                    ) : null}
                  </View>
                </Pressable>
              );
            })}
          </View>
        ))}

        {sections.length === 0 ? <Text style={[s.muted, s.empty]}>No dishes match. Try removing a filter.</Text> : null}
        <Text style={[s.muted, s.foot]}>Prices include tax. Please tell your server about any allergies.</Text>
      </ScrollView>

      {/* order bar */}
      {order.count > 0 ? (
        <View style={[s.barWrap, { paddingBottom: insets.bottom + 12 }]} pointerEvents="box-none">
          <Pressable style={({ pressed }) => [s.bar, pressed && { opacity: 0.9 }]} onPress={() => setOrderOpen(true)}>
            <View style={s.barCount}>
              <Text style={s.barTxt}>{order.count}</Text>
            </View>
            <Text style={s.barTxt}>View order</Text>
            <Text style={[s.barTxt, { fontVariant: ['tabular-nums'] }]}>{money(order.total)}</Text>
          </Pressable>
        </View>
      ) : null}

      <Animated.View pointerEvents="none" style={[s.toast, { top: insets.top + 8, transform: [{ translateY: toastY }] }]}>
        <Text style={s.toastTxt}>{toastMsg}</Text>
      </Animated.View>

      <ItemSheet item={openItem} onClose={() => setOpenItem(null)} onAdded={toast} />
      <OrderSheet visible={orderOpen} table={table} onClose={() => setOrderOpen(false)} onSend={sendOrder} />
    </View>
  );
}

const styles = (t: Theme) =>
  StyleSheet.create({
    root: { flex: 1, backgroundColor: t.bg },
    pressed: { opacity: 0.7 },
    header: { paddingHorizontal: 16, paddingTop: 12, paddingBottom: 8, gap: 12 },
    brandRow: { flexDirection: 'row', alignItems: 'center', gap: 12 },
    brand: { fontSize: 28, fontWeight: '800', color: t.ink, letterSpacing: -0.5 },
    muted: { fontSize: 14, color: t.muted, lineHeight: 20 },
    table: { borderWidth: 1.5, borderStyle: 'dashed', borderColor: t.basil, borderRadius: 12, paddingHorizontal: 12, paddingVertical: 6, alignItems: 'center' },
    tableSmall: { fontSize: 10, letterSpacing: 1, color: t.basil, fontWeight: '600' },
    tableNum: { fontSize: 22, fontWeight: '800', color: t.basil, fontVariant: ['tabular-nums'] },
    actions: { flexDirection: 'row', gap: 8 },
    action: { flex: 1, height: 44, borderRadius: 12, borderWidth: 1, borderColor: t.line, backgroundColor: t.surface, alignItems: 'center', justifyContent: 'center' },
    actionTxt: { fontWeight: '600', color: t.ink, fontSize: 14 },
    status: { backgroundColor: t.basilSoft, borderRadius: 12, paddingHorizontal: 12, paddingVertical: 10 },
    statusTxt: { color: t.basil, fontSize: 14, fontWeight: '500' },
    rail: { backgroundColor: t.bg, paddingTop: 8, paddingBottom: 10, gap: 10, borderBottomWidth: StyleSheet.hairlineWidth, borderBottomColor: t.line },
    search: { marginHorizontal: 16, height: 44, borderRadius: 12, borderWidth: 1, borderColor: t.line, backgroundColor: t.surface, paddingHorizontal: 14, fontSize: 15, color: t.ink },
    chips: { paddingHorizontal: 16, gap: 6 },
    chip: { paddingHorizontal: 14, height: 36, borderRadius: 18, borderWidth: 1, borderColor: t.line, backgroundColor: t.surface, justifyContent: 'center' },
    chipOn: { backgroundColor: t.basil, borderColor: t.basil },
    chipTxt: { fontWeight: '600', fontSize: 14, color: t.ink },
    chipTxtOn: { color: t.onBasil },
    filters: { paddingHorizontal: 16, gap: 6 },
    ftag: { paddingHorizontal: 10, height: 28, borderRadius: 8, borderWidth: 1, borderStyle: 'dashed', borderColor: t.line, justifyContent: 'center' },
    ftagOn: { borderStyle: 'solid', borderColor: t.ember, backgroundColor: t.emberSoft },
    ftagTxt: { fontSize: 12, fontWeight: '500', color: t.muted },
    section: { paddingHorizontal: 16, paddingTop: 22 },
    h2: { fontSize: 21, fontWeight: '800', color: t.ink, letterSpacing: -0.3, marginBottom: 2 },
    item: { flexDirection: 'row', gap: 14, paddingVertical: 14, alignItems: 'flex-start' },
    itemBorder: { borderTopWidth: StyleSheet.hairlineWidth, borderTopColor: t.line },
    nameRow: { flexDirection: 'row', flexWrap: 'wrap', alignItems: 'center', gap: 6 },
    itemName: { fontSize: 16, fontWeight: '600', color: t.ink },
    pop: { fontSize: 10, fontWeight: '700', letterSpacing: 0.6, color: t.emberInk, backgroundColor: t.ember, paddingHorizontal: 6, paddingVertical: 2, borderRadius: 5, overflow: 'hidden' },
    out: { fontSize: 10, fontWeight: '700', letterSpacing: 0.6, color: t.muted, backgroundColor: t.line, paddingHorizontal: 6, paddingVertical: 2, borderRadius: 5, overflow: 'hidden' },
    desc: { fontSize: 14, color: t.muted, lineHeight: 19 },
    metaRow: { flexDirection: 'row', alignItems: 'center', gap: 8, flexWrap: 'wrap' },
    price: { fontSize: 15, fontWeight: '600', color: t.ink, fontVariant: ['tabular-nums'] },
    diet: { fontSize: 10, fontWeight: '700', color: t.basil, borderWidth: 1, borderColor: t.basil, borderRadius: 4, paddingHorizontal: 4, overflow: 'hidden' },
    qtyBadge: { position: 'absolute', left: 4, top: 4, minWidth: 22, height: 22, borderRadius: 11, backgroundColor: t.basil, alignItems: 'center', justifyContent: 'center', paddingHorizontal: 6 },
    qtyTxt: { color: t.onBasil, fontSize: 12, fontWeight: '700' },
    addBtn: { position: 'absolute', right: 4, bottom: 4, width: 30, height: 30, borderRadius: 15, backgroundColor: t.surface, alignItems: 'center', justifyContent: 'center', shadowColor: '#000', shadowOpacity: 0.18, shadowRadius: 6, shadowOffset: { width: 0, height: 2 }, elevation: 3 },
    addTxt: { color: t.basil, fontSize: 20, fontWeight: '700', marginTop: -2 },
    empty: { textAlign: 'center', paddingVertical: 40 },
    foot: { textAlign: 'center', fontSize: 12, paddingTop: 28, paddingHorizontal: 16 },
    barWrap: { position: 'absolute', left: 0, right: 0, bottom: 0, paddingHorizontal: 16, paddingTop: 12 },
    bar: { height: 56, borderRadius: 16, backgroundColor: t.basil, flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingHorizontal: 16, shadowColor: '#000', shadowOpacity: 0.2, shadowRadius: 14, shadowOffset: { width: 0, height: 6 }, elevation: 8 },
    barCount: { minWidth: 30, height: 26, borderRadius: 8, backgroundColor: 'rgba(255,255,255,0.22)', alignItems: 'center', justifyContent: 'center', paddingHorizontal: 8 },
    barTxt: { color: t.onBasil, fontWeight: '700', fontSize: 15 },
    toast: { position: 'absolute', alignSelf: 'center', backgroundColor: t.ink, borderRadius: 12, paddingHorizontal: 16, paddingVertical: 10, maxWidth: '90%' },
    toastTxt: { color: t.bg, fontWeight: '600', fontSize: 14 },
  });
