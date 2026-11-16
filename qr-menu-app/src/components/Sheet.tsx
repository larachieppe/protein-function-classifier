import { ReactNode } from 'react';
import { KeyboardAvoidingView, Modal, Platform, Pressable, ScrollView, StyleSheet, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { useTheme } from '../theme';

/** Bottom sheet: slides up over a dimmed backdrop; tap outside or swipe back to close. */
export function Sheet({ visible, onClose, children, footer }: { visible: boolean; onClose: () => void; children: ReactNode; footer?: ReactNode }) {
  const t = useTheme();
  const insets = useSafeAreaInsets();
  return (
    <Modal visible={visible} transparent animationType="slide" onRequestClose={onClose} statusBarTranslucent>
      <KeyboardAvoidingView style={styles.root} behavior={Platform.OS === 'ios' ? 'padding' : undefined}>
        <Pressable style={[StyleSheet.absoluteFill, { backgroundColor: t.scrim }]} onPress={onClose} accessibilityLabel="Close" />
        <View style={[styles.sheet, { backgroundColor: t.surface, paddingBottom: 16 + insets.bottom }]}>
          <View style={[styles.grab, { backgroundColor: t.line }]} />
          <ScrollView contentContainerStyle={styles.content} keyboardShouldPersistTaps="handled" bounces={false}>
            {children}
          </ScrollView>
          {footer ? <View style={styles.footer}>{footer}</View> : null}
        </View>
      </KeyboardAvoidingView>
    </Modal>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, justifyContent: 'flex-end' },
  sheet: { maxHeight: '90%', borderTopLeftRadius: 24, borderTopRightRadius: 24, paddingTop: 10 },
  grab: { width: 40, height: 5, borderRadius: 3, alignSelf: 'center', marginBottom: 12 },
  content: { paddingHorizontal: 20, paddingBottom: 8 },
  footer: { paddingHorizontal: 20, paddingTop: 8 },
});
