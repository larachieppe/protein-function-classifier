import { StatusBar } from 'expo-status-bar';
import { useState } from 'react';
import { SafeAreaProvider } from 'react-native-safe-area-context';
import { MenuScreen } from './src/screens/MenuScreen';
import { ScanScreen } from './src/screens/ScanScreen';
import { OrderProvider } from './src/state/order';

export default function App() {
  const [table, setTable] = useState<string | null>(null);

  return (
    <SafeAreaProvider>
      <StatusBar style="auto" />
      {table ? (
        <OrderProvider key={table} table={table}>
          <MenuScreen table={table} onChangeTable={() => setTable(null)} />
        </OrderProvider>
      ) : (
        <ScanScreen onTable={setTable} />
      )}
    </SafeAreaProvider>
  );
}
