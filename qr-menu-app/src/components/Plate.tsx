import { StyleSheet, View, ViewStyle } from 'react-native';

/** Placeholder dish artwork drawn from a hue. Replace with <Image> once real photos exist. */
export function Plate({ hue, size, radius = 14, style }: { hue: number; size: number | '100%'; radius?: number; style?: ViewStyle }) {
  const h2 = (hue + 60) % 360;
  const h3 = (hue + 140) % 360;
  return (
    <View
      style={[
        styles.box,
        { width: size, aspectRatio: 1, borderRadius: radius, backgroundColor: `hsl(${h2}, 28%, 76%)` },
        style,
      ]}
    >
      <View style={[styles.plate]}>
        <View style={[styles.food, { backgroundColor: `hsl(${hue}, 55%, 48%)`, borderColor: `hsl(${hue}, 60%, 62%)` }]}>
          <View style={[styles.dot, { left: '22%', top: '25%', backgroundColor: `hsla(${hue}, 70%, 82%, 0.9)` }]} />
          <View style={[styles.dot, { right: '20%', bottom: '24%', backgroundColor: `hsl(${h3}, 55%, 38%)` }]} />
          <View style={[styles.dotSm, { right: '30%', top: '20%', backgroundColor: `hsl(${h3}, 50%, 32%)` }]} />
        </View>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  box: { overflow: 'hidden', alignItems: 'center', justifyContent: 'center' },
  plate: {
    width: '86%',
    aspectRatio: 1,
    borderRadius: 999,
    backgroundColor: '#FFFFFF',
    borderWidth: 2,
    borderColor: '#E4E8E1',
    alignItems: 'center',
    justifyContent: 'center',
  },
  food: { width: '64%', aspectRatio: 1, borderRadius: 999, borderWidth: 4 },
  dot: { position: 'absolute', width: '18%', aspectRatio: 1, borderRadius: 999 },
  dotSm: { position: 'absolute', width: '12%', aspectRatio: 1, borderRadius: 999 },
});
