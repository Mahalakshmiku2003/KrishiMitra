import React, { useState } from 'react';
import { 
  View, 
  Text, 
  StyleSheet, 
  TextInput, 
  TouchableOpacity, 
  ActivityIndicator,
  ScrollView,
  SafeAreaView,
  Platform
} from 'react-native';
import Slider from '@react-native-community/slider';
import { MaterialIcons } from '@expo/vector-icons';
import Toast from 'react-native-toast-message';
import { getNearbyMandis } from '../api/market';
import RankedMandiCard from '../components/RankedMandiCard';
import EmptyState from '../components/EmptyState';
import { theme } from '../theme';

const NearbyMandisScreen = ({ navigation }) => {
  const [location, setLocation] = useState('Nashik');
  const [commodity, setCommodity] = useState('Tomato');
  const [radius, setRadius] = useState(100);
  const [results, setResults] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const handleSearch = async () => {
    if (!location.trim()) {
      Toast.show({ type: 'error', text1: 'Missing Location', text2: 'Please enter your location' });
      return;
    }
    if (!commodity.trim()) {
      Toast.show({ type: 'error', text1: 'Missing Crop', text2: 'Please enter a crop name' });
      return;
    }

    setLoading(true);
    setError(null);
    setResults([]);

    try {
      const response = await getNearbyMandis(location, commodity, radius);
      if (response.data && response.data.status === 'success') {
        const data = response.data.mandis || response.data.top_mandis || [];
        setResults(data);
        if (data.length > 0) {
          Toast.show({ type: 'success', text1: 'Mandis Found', text2: `Ranked top ${data.length} profitable markets` });
        }
      } else {
        setResults([]);
      }
    } catch (err) {
      console.error(err);
      setError("Could not fetch mandis. Check your connection.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <SafeAreaView style={styles.safeArea}>
      <View style={styles.header}>
        <TouchableOpacity 
          style={styles.backBtn} 
          onPress={() => navigation.goBack()}
          activeOpacity={0.7}
        >
          <MaterialIcons name="arrow-back" size={24} color={theme.colors.primary} />
        </TouchableOpacity>
        <Text style={styles.headerTitle}>Nearby Mandis</Text>
      </View>

      <ScrollView style={styles.container} contentContainerStyle={styles.content} keyboardShouldPersistTaps="handled" showsVerticalScrollIndicator={false}>
        
        {/* Input Card */}
        <View style={styles.inputCard}>
          <View style={styles.inputGroup}>
            <Text style={styles.label}>YOUR LOCATION</Text>
            <View style={styles.inputWrapper}>
              <MaterialIcons name="location-on" size={20} color={theme.colors.primary} style={styles.inputIcon} />
              <TextInput 
                style={styles.input} 
                placeholder="e.g. Nashik, Maharashtra" 
                placeholderTextColor={theme.colors.onSurfaceVariant}
                value={location}
                onChangeText={setLocation}
              />
            </View>
          </View>

          <View style={styles.inputGroup}>
            <Text style={styles.label}>CROP TYPE</Text>
            <View style={styles.inputWrapper}>
              <MaterialIcons name="agriculture" size={20} color={theme.colors.primary} style={styles.inputIcon} />
              <TextInput 
                style={styles.input} 
                placeholder="e.g. Tomato, Wheat"
                placeholderTextColor={theme.colors.onSurfaceVariant}
                value={commodity}
                onChangeText={setCommodity}
              />
            </View>
          </View>

          <View style={styles.inputGroup}>
            <View style={styles.sliderHeader}>
              <Text style={styles.label}>SEARCH RADIUS</Text>
              <Text style={styles.radiusValue}>{radius} km</Text>
            </View>
            <Slider
              style={styles.slider}
              minimumValue={50}
              maximumValue={500}
              step={10}
              value={radius}
              onValueChange={setRadius}
              minimumTrackTintColor={theme.colors.primary}
              maximumTrackTintColor={theme.colors.surfaceContainerHighest}
              thumbTintColor={theme.colors.primary}
            />
          </View>

          <TouchableOpacity 
            style={[styles.searchBtn, (loading || !location || !commodity) && styles.disabledBtn]} 
            onPress={handleSearch}
            disabled={loading}
            activeOpacity={0.9}
          >
            {loading ? <ActivityIndicator color={theme.colors.onPrimaryContainer} /> : <Text style={styles.searchBtnText}>Find Best Mandis</Text>}
          </TouchableOpacity>
        </View>

        {/* Results Section */}
        {results.length > 0 && (
          <View style={styles.resultsHeader}>
            <Text style={styles.resultsTitle}>Recommended Markets</Text>
            <Text style={styles.note}>Ranked by estimated net profit after transport</Text>
          </View>
        )}

        {results.map((item, index) => (
          <RankedMandiCard 
            key={index}
            rank={index + 1}
            mandi={item.market}
            district={item.district || item.state}
            price={item.modal_price}
            transportCost={item.transport_cost}
            netPrice={item.net_price}
          />
        ))}

        {!loading && (results.length === 0 || error) && (
          <EmptyState 
            icon="location-off" 
            title={error ? "Search Error" : "No mandis nearby"} 
            subtitle={error ? error : "Try increasing the search radius or check for different crops."} 
          />
        )}

        {results.length > 0 && (
          <Text style={styles.bottomNote}>
            * Net price = mandi price minus estimated transport cost based on distance.
          </Text>
        )}
        
        {/* Bottom padding for tab bar */}
        <View style={{height: 100}} />
      </ScrollView>
    </SafeAreaView>
  );
};

const styles = StyleSheet.create({
  safeArea: {
    flex: 1,
    backgroundColor: theme.colors.surfaceContainerLow,
    paddingTop: Platform.OS === 'android' ? 40 : 0,
  },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 16,
    paddingVertical: 12,
    backgroundColor: theme.colors.surfaceContainerLow,
    zIndex: 10,
  },
  backBtn: {
    padding: 8,
    marginLeft: -8,
  },
  headerTitle: {
    fontSize: 20,
    fontWeight: '800',
    color: theme.colors.primary,
    letterSpacing: -0.5,
    marginLeft: 8,
  },
  container: {
    flex: 1,
  },
  content: {
    paddingHorizontal: 20,
    paddingTop: 16,
    gap: 24,
  },
  inputCard: {
    backgroundColor: theme.colors.surfaceContainerLowest,
    borderRadius: 12,
    padding: 24,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.04,
    shadowRadius: 20,
    elevation: 2,
    gap: 20,
  },
  inputGroup: {
    gap: 4,
  },
  label: {
    fontSize: 10,
    fontWeight: '700',
    color: theme.colors.onSurfaceVariant,
    textTransform: 'uppercase',
    letterSpacing: 0.5,
    marginLeft: 4,
  },
  inputWrapper: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: theme.colors.surfaceContainerHighest,
    borderRadius: 8,
    paddingHorizontal: 16,
    height: 48,
  },
  inputIcon: {
    marginRight: 8,
  },
  input: {
    flex: 1,
    fontSize: 16,
    fontWeight: '500',
    color: theme.colors.onSurface,
  },
  sliderHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 8,
  },
  radiusValue: {
    fontSize: 14,
    fontWeight: '700',
    color: theme.colors.primary,
  },
  slider: {
    width: '100%',
    height: 40,
  },
  searchBtn: {
    backgroundColor: theme.colors.primaryContainer,
    height: 56,
    borderRadius: 999,
    justifyContent: 'center',
    alignItems: 'center',
    marginTop: 8,
    shadowColor: theme.colors.primary,
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.2,
    shadowRadius: 12,
    elevation: 4,
  },
  disabledBtn: {
    backgroundColor: theme.colors.surfaceVariant,
    shadowOpacity: 0,
    elevation: 0,
  },
  searchBtnText: {
    color: theme.colors.onPrimaryContainer,
    fontWeight: '800',
    fontSize: 16,
  },
  resultsHeader: {
    paddingHorizontal: 4,
  },
  resultsTitle: {
    fontSize: 20,
    fontWeight: '800',
    color: theme.colors.onSurface,
    letterSpacing: -0.5,
  },
  note: {
    fontSize: 12,
    fontWeight: '500',
    color: theme.colors.onSurfaceVariant,
    marginTop: 4,
  },
  bottomNote: {
    paddingVertical: 16,
    fontSize: 11,
    color: theme.colors.outline,
    textAlign: 'center',
    fontStyle: 'italic',
  }
});

export default NearbyMandisScreen;
