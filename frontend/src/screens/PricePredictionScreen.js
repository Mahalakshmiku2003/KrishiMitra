import React, { useState } from 'react';
import { 
  View, 
  Text, 
  StyleSheet, 
  TextInput, 
  TouchableOpacity, 
  ScrollView, 
  Dimensions,
  ActivityIndicator
} from 'react-native';
import { LineChart } from 'react-native-chart-kit';
import { Ionicons } from '@expo/vector-icons';
import Toast from 'react-native-toast-message';
import { getPricePrediction } from '../api/market';
import EmptyState from '../components/EmptyState';

const { width } = Dimensions.get('window');

const PricePredictionScreen = ({ navigation }) => {
  const [commodity, setCommodity] = useState('Tomato');
  const [market, setMarket] = useState('Nashik');
  const [loading, setLoading] = useState(false);
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);

  const fetchPrediction = async () => {
    if (!commodity.trim() || !market.trim()) {
      Toast.show({ type: 'error', text1: 'Missing info', text2: 'Please enter crop and market names' });
      return;
    }

    setLoading(true);
    setError(null);
    setData(null);

    try {
      const response = await getPricePrediction(commodity, market);
      if (response.data && response.data.status === 'success' && response.data.forecast && response.data.forecast.length > 0) {
        setData(response.data.forecast);
        Toast.show({ type: 'success', text1: 'Forecast ready', text2: `7-day trend for ${commodity}` });
      } else {
        const errorMsg = response.data?.message || "No prediction data available for this market.";
        setError(errorMsg);
      }
    } catch (err) {
      console.error(err);
      setError("Failed to fetch forecast. Check your connection.");
    } finally {
      setLoading(false);
    }
  };

  const dayNames = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
  const getDayLabel = (dateStr) => {
    if (!dateStr) return "";
    const d = new Date(dateStr);
    return dayNames[d.getDay()];
  };

  const renderTrend = () => {
    if (!data || data.length < 2) return null;
    const start = data[0]?.predicted_price || 0;
    const end = data[data.length - 1]?.predicted_price || 0;
    const isRising = end > start;

    return (
      <View style={styles.trendCard}>
        <Text style={[styles.trendValue, { color: isRising ? '#2E7D32' : '#C62828' }]}>
          {isRising ? '📈 Rising' : '📉 Falling'}
        </Text>
        <Text style={styles.trendSub}>7-Day Trend</Text>
      </View>
    );
  };

  return (
    <View style={styles.container}>
      <View style={styles.header}>
        <TouchableOpacity style={styles.backBtn} onPress={() => navigation.goBack()}>
          <Ionicons name="arrow-back" size={24} color="#333" />
        </TouchableOpacity>
        <Text style={styles.headerTitle}>Price Forecast</Text>
      </View>

      <ScrollView contentContainerStyle={styles.content}>
        <View style={styles.searchSection}>
          <Text style={styles.label}>Crop Name</Text>
          <TextInput 
            style={styles.input} 
            placeholder="e.g. Tomato" 
            value={commodity}
            onChangeText={setCommodity}
          />
          <Text style={styles.label}>Market Name</Text>
          <TextInput 
            style={styles.input} 
            placeholder="e.g. Nashik" 
            value={market}
            onChangeText={setMarket}
          />
          <TouchableOpacity style={styles.btn} onPress={fetchPrediction} disabled={loading}>
            {loading ? <ActivityIndicator color="#FFF" /> : <Text style={styles.btnText}>Get Forecast</Text>}
          </TouchableOpacity>
        </View>

        {loading && (
          <View style={styles.loadingContainer}>
            <ActivityIndicator size="large" color="#2E7D32" />
            <Text style={styles.loadingText}>Analyzing market trends...</Text>
          </View>
        )}

        {data && data.length > 0 && !loading && (
          <View style={styles.chartSection}>
            <LineChart
              data={{
                labels: data.map(item => getDayLabel(item.date)),
                datasets: [{ data: data.map(item => item.predicted_price || 0) }]
              }}
              width={width - 32}
              height={220}
              yAxisLabel="₹"
              chartConfig={{
                backgroundColor: '#FFFFFF',
                backgroundGradientFrom: '#FFFFFF',
                backgroundGradientTo: '#FFFFFF',
                decimalPlaces: 0,
                color: (opacity = 1) => `rgba(46, 125, 50, ${opacity})`,
                labelColor: (opacity = 1) => `rgba(0, 0, 0, ${opacity})`,
                style: { borderRadius: 16 },
                propsForDots: { r: "5", strokeWidth: "2", stroke: "#2E7D32" }
              }}
              bezier
              style={styles.chart}
            />

            <View style={styles.summaryRow}>
              <View style={styles.summaryCard}>
                <Text style={styles.summaryValue}>₹{data[0]?.predicted_price}</Text>
                <Text style={styles.summaryLabel}>Today</Text>
              </View>
              <View style={styles.summaryCard}>
                <Text style={styles.summaryValue}>₹{data[data.length - 1]?.predicted_price}</Text>
                <Text style={styles.summaryLabel}>Day 7</Text>
              </View>
              {renderTrend()}
            </View>
          </View>
        )}

        {!loading && !data && !error && (
          <EmptyState 
            icon="📈" 
            title="Forecast your profits" 
            subtitle="Search for a crop and market to see predicted prices for the next 7 days."
          />
        )}

        {error && (
          <EmptyState 
            icon="❌" 
            title="Analysis Unavailable" 
            subtitle={error}
          />
        )}
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
  content: { padding: 16 },
  searchSection: { backgroundColor: '#FFF', padding: 20, borderRadius: 12, elevation: 2, marginBottom: 20 },
  label: { fontSize: 14, fontWeight: 'bold', color: '#666', marginBottom: 8 },
  input: { 
    height: 48, 
    backgroundColor: '#FAFAFA', 
    borderRadius: 8, 
    borderWidth: 1, 
    borderColor: '#EEE', 
    paddingHorizontal: 16, 
    marginBottom: 16 
  },
  btn: { 
    backgroundColor: '#2E7D32', 
    height: 50, 
    borderRadius: 8, 
    justifyContent: 'center', 
    alignItems: 'center',
    elevation: 2
  },
  btnText: { color: '#FFF', fontWeight: 'bold', fontSize: 16 },
  loadingContainer: { padding: 40, alignItems: 'center' },
  loadingText: { marginTop: 12, color: '#666' },
  chartSection: { alignItems: 'center' },
  chart: { marginVertical: 8, borderRadius: 12 },
  summaryRow: { flexDirection: 'row', justifyContent: 'space-between', width: '100%', marginTop: 20 },
  summaryCard: { 
    flex: 0.31, 
    backgroundColor: '#FFF', 
    padding: 12, 
    borderRadius: 12, 
    alignItems: 'center',
    elevation: 2
  },
  summaryValue: { fontSize: 16, fontWeight: 'bold', color: '#333' },
  summaryLabel: { fontSize: 10, color: '#9E9E9E', marginTop: 4, textTransform: 'uppercase' },
  trendCard: { 
    flex: 0.31, 
    backgroundColor: '#FFF', 
    padding: 12, 
    borderRadius: 12, 
    alignItems: 'center',
    elevation: 2,
    borderWidth: 1,
    borderColor: '#F5F5F5'
  },
  trendValue: { fontSize: 14, fontWeight: 'bold' },
  trendSub: { fontSize: 10, color: '#9E9E9E', marginTop: 4, textTransform: 'uppercase' }
});

export default PricePredictionScreen;
