export const theme = {
  colors: {
    primary: '#0d631b',
    primaryContainer: '#2e7d32',
    onPrimary: '#ffffff',
    onPrimaryContainer: '#cbffc2',
    secondary: '#2a6b2c',
    secondaryContainer: '#acf4a4',
    tertiary: '#774c00',
    tertiaryFixed: '#ffddb5',
    onTertiary: '#ffffff',
    surface: '#f9f9f9',
    surfaceVariant: '#e2e2e2',
    onSurface: '#1a1c1c',
    onSurfaceVariant: '#40493d',
    surfaceContainerLowest: '#ffffff',
    surfaceContainerLow: '#f3f3f3',
    surfaceContainer: '#eeeeee',
    surfaceContainerHigh: '#e8e8e8',
    surfaceContainerHighest: '#e2e2e2',
    error: '#ba1a1a',
    onError: '#ffffff',
    outline: '#707a6c',
    outlineVariant: '#bfcaba',
    background: '#f9f9f9'
  },
  typography: {
    headline: {
      fontWeight: '700',
      // We rely on system fonts or default React Native fonts for now to avoid setup overhead
    },
    body: {
      fontWeight: '400',
    },
    label: {
      fontWeight: '600',
      textTransform: 'uppercase',
      letterSpacing: 1
    }
  },
  spacing: {
    xs: 4,
    sm: 8,
    md: 16,
    lg: 24,
    xl: 32,
    xxl: 48
  },
  borderRadius: {
    sm: 4,
    md: 8,
    lg: 12,
    xl: 16,
    xxl: 24,
    full: 9999
  }
};
