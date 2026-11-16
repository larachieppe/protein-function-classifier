import { useColorScheme } from 'react-native';

const light = {
  bg: '#F7F8F4',
  surface: '#FFFFFF',
  ink: '#18211C',
  muted: '#5E6B63',
  line: '#E2E6DF',
  basil: '#1F5A40',
  basilSoft: '#E3EEE7',
  onBasil: '#FFFFFF',
  ember: '#D9822B',
  emberInk: '#2A1A08',
  emberSoft: '#F7E6D3',
  scrim: 'rgba(10,18,14,0.45)',
};

const dark: typeof light = {
  bg: '#101512',
  surface: '#18201B',
  ink: '#EAF0EC',
  muted: '#9AA9A0',
  line: '#28332C',
  basil: '#6CC39A',
  basilSoft: '#1C3328',
  onBasil: '#0C1A13',
  ember: '#F0A04E',
  emberInk: '#1E1205',
  emberSoft: '#3A2A18',
  scrim: 'rgba(0,0,0,0.6)',
};

export type Theme = typeof light;

export function useTheme(): Theme {
  return useColorScheme() === 'dark' ? dark : light;
}
