import React, { useState } from 'react';
import { 
  View, 
  Text, 
  StyleSheet, 
  TextInput, 
  TouchableOpacity, 
  FlatList, 
  ActivityIndicator,
  ScrollView
} from 'react-native';
import Slider from '@react-native-community/slider';
import { Ionicons } from '@expo/vector-icons';
import Toast from 'react-native-toast-message';
import { getNearbyMandis } from '../api/market';
import RankedMandiCard from '../components/RankedMandiCard';
import EmptyState from '../components/EmptyState';

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
    <View style={styles.container}>
      <View style={styles.header}>
        <TouchableOpacity style={styles.backBtn} onPress={() => navigation.goBack()}>
          <Ionicons name="arrow-back" size={24} color="#333" />
        </TouchableOpacity>
        <Text style={styles.headerTitle}>Nearby Mandis</Text>
      </View>

      <ScrollView style={styles.form} keyboardShouldPersistTaps="handled">
        <View style={styles.section}>
          <Text style={styles.label}>Your Location</Text>
          <TextInput 
            style={styles.input} 
            placeholder="e.g. Nashik, Maharashtra" 
            value={location}
            onChangeText={setLocation}
          />
          
          <Text style={styles.label}>Crop Type</Text>
          <TextInput 
            style={styles.input} 
            placeholder="e.g. Tomato, Wheat" 
            value={commodity}
            onChangeText={setCommodity}
          />

          <View style={styles.sliderHeader}>
            <Text style={styles.label}>Search Radius</Text>
            <Text style={styles.radiusValue}>{radius} km</Text>
          </View>
          <Slider
            style={styles.slider}
            minimumValue={50}
            maximumValue={200}
            step={10}
            value={radius}
            onValueChange={setRadius}
            minimumTrackTintColor="#2E7D32"
            maximumTrackTintColor="#EEE"
            thumbTintColor="#2E7D32"
          />

          <TouchableOpacity 
            style={[styles.searchBtn, (loading || !location || !commodity) && styles.disabledBtn]} 
            onPress={handleSearch}
            disabled={loading}
          >
            {loading ? <ActivityIndicator color="#FFF" /> : <Text style={styles.searchBtnText}>Find Best Mandis</Text>}
          </TouchableOpacity>
        </View>

        {results.length > 0 && (
          <View style={styles.resultsHeader}>
            <Text style={styles.resultsTitle}>Recommended Markets</Text>
            <Text style={styles.note}>Ranked by estimated net profit after transport</Text>
          </View>
        )}

        {results.map((item, index) => (
          <View key={index} style={styles.cardWrapper}>
            <RankedMandiCard 
              rank={index + 1}
              mandi={item.market}
              district={item.district || item.state}
              price={item.modal_price}
              transportCost={item.transport_cost}
              netPrice={item.net_price}
            />
          </View>
        ))}

        {!loading && (results.length === 0 || error) && (
          <EmptyState 
            icon="📍" 
            title={error ? "Search Error" : "No mandis nearby"} 
            subtitle={error ? error : "Try increasing the search radius or check for different crops."} 
          />
        )}

        {results.length > 0 && (
          <Text style={styles.bottomNote}>
            * Net price = mandi price minus estimated transport cost based on distance.
          </Text>
        )}
        
        <View style={{ height: 40 }} />
      </ScrollView>
    </View>
  );
};

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#F5F5F5' },
  header: { 
    height: 100, 
    flexDirection: 'row', 
    alignItems: 'center', 
    paddingTop: 40, 
    paddingHorizontal: 20, 
    backgroundColor: '#FFF' 
  },
  backBtn: { padding: 8 },
  headerTitle: { fontSize: 20, fontWeight: 'bold', marginLeft: 10, color: '#333' },
  form: { flex: 1 },
  section: { padding: 20, backgroundColor: '#FFF', borderBottomWidth: 1, borderBottomColor: '#EEE' },
  label: { fontSize: 14, fontWeight: 'bold', color: '#666', marginBottom: 8 },
  input: { 
    height: 48, 
    backgroundColor: '#FAFAFA', 
    borderRadius: 8, 
    borderWidth: 1, 
    borderColor: '#EEE', 
    paddingHorizontal: 16, 
    marginBottom: 20,
    fontSize: 15
  },
  sliderHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  radiusValue: { color: '#2E7D32', fontWeight: 'bold' },
  slider: { width: '100%', height: 40, marginBottom: 20 },
  searchBtn: { 
    backgroundColor: '#2E7D32', 
    height: 50, 
    borderRadius: 8, 
    justifyContent: 'center', 
    alignItems: 'center',
    elevation: 2
  },
  disabledBtn: { backgroundColor: '#A5D6A7' },
  searchBtnText: { color: '#FFF', fontWeight: 'bold', fontSize: 16 },
  resultsHeader: { paddingHorizontal: 20, paddingTop: 20, marginBottom: 10 },
  resultsTitle: { fontSize: 18, fontWeight: 'bold', color: '#333' },
  note: { fontSize: 12, color: '#9E9E9E', marginTop: 4 },
  cardWrapper: { paddingHorizontal: 20 },
  bottomNote: { padding: 20, fontSize: 11, color: '#999', textAlign: 'center', fontStyle: 'italic' }
});

export default NearbyMandisScreen;
