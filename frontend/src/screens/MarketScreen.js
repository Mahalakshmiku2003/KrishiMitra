import React, { useState, useEffect } from 'react';
import { 
  View, 
  Text, 
  StyleSheet, 
  TextInput, 
  TouchableOpacity, 
  ScrollView, 
  ActivityIndicator,
  Dimensions,
  Alert
} from 'react-native';
import { LineChart } from 'react-native-chart-kit';
import { getLivePrices, getNearbyMandis, getPricePrediction } from '../api/market';

const { width } = Dimensions.get('window');

const MarketScreen = () => {
  const [commodity, setCommodity] = useState('Tomato');
  const [location, setLocation] = useState('Nashik');
  const [loading, setLoading] = useState(false);
  
  const [liveData, setLiveData] = useState(null);
  const [nearbyData, setNearbyData] = useState(null);
  const [predictionData, setPredictionData] = useState(null);

  const fetchMarketData = async () => {
    if (!commodity) return;
    setLoading(true);
    try {
      // 1. Fetch Live Prices
      const liveRes = await getLivePrices(commodity);
      setLiveData(liveRes.data);

      // 2. Fetch Nearby (Best Market)
      if (location) {
        const nearbyRes = await getNearbyMandis(commodity, location);
        setNearbyData(nearbyRes.data);
      }

      // 3. Fetch Prediction (Using top market from live data if available)
      const topMarket = liveRes.data.prices?.[0]?.market || 'Default';
      const predictRes = await getPricePrediction(commodity, topMarket);
      setPredictionData(predictRes.data);

    } catch (err) {
      console.error(err);
      Alert.alert('Data Error', 'Could not fetch market data. Please check your connection.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchMarketData();
  }, []);

  const renderSectionHeader = (title) => (
    <Text style={styles.sectionTitle}>{title}</Text>
  );

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      <Text style={styles.header}>Market Intelligence</Text>
      
      {/* Search Bar */}
      <View style={styles.searchContainer}>
        <TextInput 
          style={styles.input} 
          placeholder="Crop (e.g. Tomato)" 
          value={commodity}
          onChangeText={setCommodity}
        />
        <TextInput 
          style={styles.input} 
          placeholder="Your Location (e.g. Nashik)" 
          value={location}
          onChangeText={setLocation}
        />
        <TouchableOpacity style={styles.searchButton} onPress={fetchMarketData}>
          {loading ? <ActivityIndicator color="#FFF" /> : <Text style={styles.searchButtonText}>Search</Text>}
        </TouchableOpacity>
      </View>

      {liveData && liveData.status === 'success' && (
        <View style={styles.section}>
          {renderSectionHeader('Live Prices')}
          <View style={styles.statsRow}>
            <View style={styles.statBox}>
              <Text style={styles.statLabel}>Avg Price</Text>
              <Text style={styles.statValue}>₹{liveData.summary.avg_price}</Text>
            </View>
            <View style={styles.statBox}>
              <Text style={styles.statLabel}>Max Price</Text>
              <Text style={[styles.statValue, { color: '#2E7D32' }]}>₹{liveData.summary.max_price}</Text>
            </View>
            <View style={styles.statBox}>
              <Text style={styles.statLabel}>Min Price</Text>
              <Text style={[styles.statValue, { color: '#D32F2F' }]}>₹{liveData.summary.min_price}</Text>
            </View>
          </View>
        </View>
      )}

      {nearbyData && nearbyData.status === 'success' && (
        <View style={styles.section}>
          {renderSectionHeader('Best Selling Opportunity')}
          <View style={styles.recommendationCard}>
            <Text style={styles.bestMarketName}>{nearbyData.best_market.market}</Text>
            <Text style={styles.bestMarketSub}>{nearbyData.best_market.state} • {nearbyData.best_market.distance_km}km away</Text>
            
            <View style={styles.priceBreakdown}>
              <View style={styles.priceItem}>
                <Text style={styles.priceLabel}>Mandi Price</Text>
                <Text style={styles.priceValueBold}>₹{nearbyData.best_market.modal_price}</Text>
              </View>
              <Text style={styles.minus}>-</Text>
              <View style={styles.priceItem}>
                <Text style={styles.priceLabel}>Transport</Text>
                <Text style={styles.priceValueBold}>₹{nearbyData.best_market.transport_cost}</Text>
              </View>
              <Text style={styles.equal}>=</Text>
              <View style={styles.priceItem}>
                <Text style={styles.priceLabel}>Net Profit</Text>
                <Text style={[styles.priceValueBold, { color: '#2E7D32' }]}>₹{nearbyData.best_market.net_price}</Text>
              </View>
            </View>
            
            <Text style={styles.recommendationText}>{nearbyData.recommendation}</Text>
          </View>
        </View>
      )}

      {predictionData && predictionData.status === 'success' && (
        <View style={styles.section}>
          {renderSectionHeader('7-Day Price Forecast')}
          <View style={styles.chartContainer}>
            <LineChart
              data={{
                labels: predictionData.forecast.map(f => f.date.split('-')[2]), // Day strictly
                datasets: [{ data: predictionData.forecast.map(f => f.predicted_price) }]
              }}
              width={width - 48}
              height={220}
              yAxisLabel="₹"
              chartConfig={{
                backgroundColor: '#FFFFFF',
                backgroundGradientFrom: '#FFFFFF',
                backgroundGradientTo: '#FFFFFF',
                decimalPlaces: 0,
                color: (opacity = 1) => `rgba(249, 168, 37, ${opacity})`, // Accent color
                labelColor: (opacity = 1) => `rgba(0, 0, 0, ${opacity})`,
                style: { borderRadius: 16 },
                propsForDots: { r: "6", strokeWidth: "2", stroke: "#F9A825" }
              }}
              bezier
              style={{ marginVertical: 8, borderRadius: 12 }}
            />
            <Text style={styles.chartCaption}>Predicted prices for {commodity} in {predictionData.market}</Text>
          </View>
        </View>
      )}

      {!loading && !liveData && (
        <View style={styles.emptyState}>
          <Text style={styles.emptyText}>Search for a crop to see market insights.</Text>
        </View>
      )}
    </ScrollView>
  );
};

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#F5F5F5' },
  content: { padding: 24, paddingTop: 60 },
  header: { fontSize: 24, fontWeight: 'bold', color: '#2E7D32', marginBottom: 20 },
  searchContainer: { 
    backgroundColor: '#FFF', 
    padding: 16, 
    borderRadius: 12, 
    elevation: 3, 
    shadowColor: '#000', 
    shadowOffset: { width: 0, height: 1 }, 
    shadowOpacity: 0.1, 
    shadowRadius: 2,
    marginBottom: 24
  },
  input: { 
    height: 48, 
    borderWidth: 1, 
    borderColor: '#EEE', 
    borderRadius: 8, 
    paddingHorizontal: 12, 
    marginBottom: 12,
    backgroundColor: '#FAFAFA'
  },
  searchButton: { 
    height: 48, 
    backgroundColor: '#2E7D32', 
    borderRadius: 8, 
    justifyContent: 'center', 
    alignItems: 'center' 
  },
  searchButtonText: { color: '#FFF', fontWeight: 'bold', fontSize: 16 },
  section: { marginBottom: 24 },
  sectionTitle: { fontSize: 18, fontWeight: 'bold', color: '#333', marginBottom: 12 },
  statsRow: { flexDirection: 'row', justifyContent: 'space-between' },
  statBox: { 
    flex: 0.3, 
    backgroundColor: '#FFF', 
    padding: 12, 
    borderRadius: 12, 
    alignItems: 'center',
    elevation: 2 
  },
  statLabel: { fontSize: 12, color: '#666', marginBottom: 4 },
  statValue: { fontSize: 16, fontWeight: 'bold' },
  recommendationCard: { 
    backgroundColor: '#FFF', 
    padding: 20, 
    borderRadius: 12, 
    elevation: 4,
    shadowColor: '#000',
    shadowOpacity: 0.1,
    shadowRadius: 4,
    borderLeftWidth: 4,
    borderLeftColor: '#F9A825'
  },
  bestMarketName: { fontSize: 20, fontWeight: 'bold', color: '#333' },
  bestMarketSub: { fontSize: 14, color: '#666', marginBottom: 16 },
  priceBreakdown: { 
    flexDirection: 'row', 
    alignItems: 'center', 
    justifyContent: 'space-between',
    backgroundColor: '#F9F9F9',
    padding: 12,
    borderRadius: 8,
    marginBottom: 16
  },
  priceItem: { alignItems: 'center' },
  priceLabel: { fontSize: 10, color: '#999', marginBottom: 4 },
  priceValueBold: { fontSize: 14, fontWeight: 'bold' },
  minus: { fontSize: 20, color: '#CCC' },
  equal: { fontSize: 20, color: '#CCC' },
  recommendationText: { fontSize: 14, color: '#2E7D32', fontStyle: 'italic', lineHeight: 20 },
  chartContainer: { 
    backgroundColor: '#FFF', 
    padding: 12, 
    borderRadius: 12, 
    elevation: 3,
    alignItems: 'center'
  },
  chartCaption: { fontSize: 12, color: '#999', marginTop: 8 },
  emptyState: { padding: 40, alignItems: 'center' },
  emptyText: { color: '#999', fontStyle: 'italic', textAlign: 'center' }
});

export default MarketScreen;
