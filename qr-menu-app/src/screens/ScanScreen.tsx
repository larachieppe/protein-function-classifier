import { CameraView, useCameraPermissions } from 'expo-camera';
import * as Haptics from 'expo-haptics';
import { useRef, useState } from 'react';
import { Pressable, StyleSheet, Text, TextInput, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { parseTable, RESTAURANT } from '../data/menu';
import { Theme, useTheme } from '../theme';

/** First screen: scan the QR code on the table, or type the table number. */
export function ScanScreen({ onTable }: { onTable: (table: string) => void }) {
  const t = useTheme();
  const s = styles(t);
  const insets = useSafeAreaInsets();
  const [permission, requestPermission] = useCameraPermissions();
  const [manual, setManual] = useState('');
  const [error, setError] = useState<string | null>(null);
  const handled = useRef(false);

  const onScan = ({ data }: { data: string }) => {
    if (handled.current) return;
    const table = parseTable(data);
    if (!table) {
      setError("That QR code isn't a table code. Try the one on your table's stand.");
      return;
    }
    handled.current = true;
    Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success).catch(() => {});
    onTable(table);
  };

  const submitManual = () => {
    const table = parseTable(manual);
    if (table) onTable(table);
    else setError('Enter the number printed on your table, for example 12.');
  };

  return (
    <View style={[s.root, { paddingTop: insets.top + 16, paddingBottom: insets.bottom + 16 }]}>
      <View style={{ gap: 4 }}>
        <Text style={s.brand}>{RESTAURANT.name}</Text>
        <Text style={s.muted}>Scan the code on your table to see the menu and order.</Text>
      </View>

      <View style={s.frame}>
        {permission?.granted ? (
          <CameraView style={StyleSheet.absoluteFill} facing="back" barcodeScannerSettings={{ barcodeTypes: ['qr'] }} onBarcodeScanned={onScan} />
        ) : (
          <View style={s.ask}>
            <Text style={s.askTitle}>Camera access</Text>
            <Text style={[s.muted, { textAlign: 'center' }]}>
              {permission && !permission.canAskAgain
                ? 'Camera access is off for this app. Turn it on in Settings, or enter your table number below.'
                : 'The camera is only used to read the QR code on your table.'}
            </Text>
            {!permission || permission.canAskAgain ? (
              <Pressable style={s.primary} onPress={requestPermission}>
                <Text style={s.primaryTxt}>Allow camera</Text>
              </Pressable>
            ) : null}
          </View>
        )}
        <View pointerEvents="none" style={s.corners}>
          <View style={[s.corner, { top: 0, left: 0, borderTopWidth: 4, borderLeftWidth: 4 }]} />
          <View style={[s.corner, { top: 0, right: 0, borderTopWidth: 4, borderRightWidth: 4 }]} />
          <View style={[s.corner, { bottom: 0, left: 0, borderBottomWidth: 4, borderLeftWidth: 4 }]} />
          <View style={[s.corner, { bottom: 0, right: 0, borderBottomWidth: 4, borderRightWidth: 4 }]} />
        </View>
      </View>

      {error ? <Text style={s.error}>{error}</Text> : null}

      <View style={{ gap: 8 }}>
        <Text style={s.label}>No code? Enter your table number</Text>
        <View style={s.row}>
          <TextInput
            style={s.input}
            value={manual}
            onChangeText={(v) => {
              setManual(v.replace(/[^0-9]/g, ''));
              setError(null);
            }}
            keyboardType="number-pad"
            placeholder="e.g. 12"
            placeholderTextColor={t.muted}
            maxLength={3}
            returnKeyType="go"
            onSubmitEditing={submitManual}
          />
          <Pressable style={[s.primary, { flex: 1 }]} onPress={submitManual}>
            <Text style={s.primaryTxt}>Open menu</Text>
          </Pressable>
        </View>
        <Pressable onPress={() => onTable('12')} hitSlop={8}>
          <Text style={s.link}>Just looking? Open the demo menu for table 12</Text>
        </Pressable>
      </View>
    </View>
  );
}

const styles = (t: Theme) =>
  StyleSheet.create({
    root: { flex: 1, backgroundColor: t.bg, paddingHorizontal: 20, gap: 18 },
    brand: { fontSize: 30, fontWeight: '800', color: t.ink, letterSpacing: -0.5 },
    muted: { fontSize: 15, color: t.muted, lineHeight: 21 },
    frame: { flex: 1, maxHeight: 420, borderRadius: 24, overflow: 'hidden', backgroundColor: t.surface, borderWidth: 1, borderColor: t.line },
    ask: { flex: 1, alignItems: 'center', justifyContent: 'center', gap: 12, padding: 28 },
    askTitle: { fontSize: 18, fontWeight: '700', color: t.ink },
    corners: { position: 'absolute', top: 28, right: 28, bottom: 28, left: 28 },
    corner: { position: 'absolute', width: 36, height: 36, borderColor: t.ember, borderRadius: 6 },
    error: { color: t.ember, fontSize: 14, fontWeight: '600' },
    label: { fontSize: 14, fontWeight: '600', color: t.ink },
    row: { flexDirection: 'row', gap: 10 },
    input: { width: 110, height: 52, borderRadius: 14, borderWidth: 1, borderColor: t.line, backgroundColor: t.surface, paddingHorizontal: 14, fontSize: 18, color: t.ink, fontVariant: ['tabular-nums'] },
    primary: { height: 52, borderRadius: 14, backgroundColor: t.basil, alignItems: 'center', justifyContent: 'center', paddingHorizontal: 20 },
    primaryTxt: { color: t.onBasil, fontWeight: '700', fontSize: 15 },
    link: { color: t.basil, fontSize: 14, fontWeight: '600', paddingVertical: 4 },
  });
