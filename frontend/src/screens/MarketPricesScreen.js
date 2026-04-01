import React, { useState, useEffect } from 'react';
import { 
  View, 
  Text, 
  StyleSheet, 
  TextInput, 
  TouchableOpacity, 
  FlatList, 
  ActivityIndicator,
  Animated,
  Dimensions
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import Toast from 'react-native-toast-message';
import { getMarketPrices } from '../api/market';
import PriceCard from '../components/PriceCard';
import EmptyState from '../components/EmptyState';

const { width } = Dimensions.get('window');

const SkeletonCard = () => {
  const opacity = new Animated.Value(0.3);
  
  useEffect(() => {
    Animated.loop(
      Animated.sequence([
        Animated.timing(opacity, { toValue: 1, duration: 800, useNativeDriver: true }),
        Animated.timing(opacity, { toValue: 0.3, duration: 800, useNativeDriver: true }),
      ])
    ).start();
  }, []);

  return (
    <Animated.View style={[styles.skeletonCard, { opacity }]}>
      <View style={styles.skeletonRow} />
      <View style={[styles.skeletonRow, { width: '60%', marginTop: 10 }]} />
    </Animated.View>
  );
};

const MarketPricesScreen = ({ navigation }) => {
  const [commodity, setCommodity] = useState('Tomato');
  const [state, setState] = useState('');
  const [results, setResults] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [sortBy, setSortBy] = useState('price');

  const handleSearch = async () => {
    if (!commodity.trim()) {
      Toast.show({ type: 'error', text1: 'Required', text2: 'Please enter a crop name' });
      return;
    }
    
    setLoading(true);
    setError(null);
    setResults([]);

    try {
      const response = await getMarketPrices(commodity, state);
      if (response.data && response.data.status === 'success') {
        const sorted = sortResults(response.data.prices, sortBy);
        setResults(sorted);
        if (sorted.length > 0) {
          Toast.show({ type: 'success', text1: '✅ Prices updated', text2: `Found ${sorted.length} markets for ${commodity}` });
        }
      } else {
        setResults([]);
      }
    } catch (err) {
      console.error(err);
      setError("Could not fetch prices. Check your connection.");
    } finally {
      setLoading(false);
    }
  };

  const sortResults = (data, method) => {
    if (method === 'price') {
      return [...data].sort((a, b) => b.modal_price - a.modal_price);
    } else {
      return [...data].sort((a, b) => new Date(b.date) - new Date(a.date));
    }
  };

  const handleSortChange = (method) => {
    setSortBy(method);
    if (results.length > 0) {
      setResults(sortResults(results, method));
    }
  };

  return (
    <View style={styles.container}>
      <View style={styles.header}>
        <TouchableOpacity style={styles.backBtn} onPress={() => navigation.goBack()}>
          <Ionicons name="arrow-back" size={24} color="#333" />
        </TouchableOpacity>
        <Text style={styles.headerTitle}>Mandi Prices</Text>
      </View>

      <View style={styles.searchSection}>
        <View style={styles.inputRow}>
          <Ionicons name="search" size={20} color="#9E9E9E" style={styles.searchIcon} />
          <TextInput 
            style={styles.input} 
            placeholder="e.g. Tomato, Onion, Wheat" 
            value={commodity}
            onChangeText={setCommodity}
          />
        </View>
        <TextInput 
          style={[styles.input, { marginTop: 12, paddingLeft: 16 }]} 
          placeholder="e.g. Maharashtra — optional" 
          value={state}
          onChangeText={setState}
        />
        <TouchableOpacity 
          style={[styles.searchBtn, !commodity && styles.disabledBtn]} 
          onPress={handleSearch}
          disabled={loading}
        >
          <Text style={styles.searchBtnText}>Search Prices</Text>
        </TouchableOpacity>
      </View>

      {results.length > 0 && !loading && (
        <View style={styles.sortSection}>
          <TouchableOpacity 
            style={[styles.sortBtn, sortBy === 'price' && styles.activeSortBtn]} 
            onPress={() => handleSortChange('price')}
          >
            <Text style={[styles.sortBtnText, sortBy === 'price' && styles.activeSortText]}>Highest Price</Text>
          </TouchableOpacity>
          <TouchableOpacity 
            style={[styles.sortBtn, sortBy === 'date' && styles.activeSortBtn]} 
            onPress={() => handleSortChange('date')}
          >
            <Text style={[styles.sortBtnText, sortBy === 'date' && styles.activeSortText]}>Most Recent</Text>
          </TouchableOpacity>
        </View>
      )}

      <FlatList
        data={loading ? [1, 2, 3] : results}
        keyExtractor={(item, index) => index.toString()}
        renderItem={({ item }) => loading ? (
          <SkeletonCard />
        ) : (
          <PriceCard 
            commodity={item.commodity}
            market={item.market}
            state={item.state}
            price={item.modal_price}
            date={item.date}
          />
        )}
        contentContainerStyle={styles.listContent}
        ListEmptyComponent={() => !loading && (
          <EmptyState 
            icon="📊" 
            title={error ? "Error Fetching Data" : "No prices found"} 
            subtitle={error ? error : "Try a different crop name or broaden your search."} 
          />
        )}
      />
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
  searchSection: { padding: 20, backgroundColor: '#FFF', borderBottomWidth: 1, borderBottomColor: '#EEE' },
  inputRow: { 
    flexDirection: 'row', 
    alignItems: 'center', 
    backgroundColor: '#FAFAFA', 
    borderWidth: 1, 
    borderColor: '#EEE', 
    borderRadius: 8, 
    paddingHorizontal: 12 
  },
  searchIcon: { marginRight: 8 },
  input: { flex: 1, height: 48, backgroundColor: '#FAFAFA', borderRadius: 8, fontSize: 15 },
  searchBtn: { 
    backgroundColor: '#2E7D32', 
    height: 50, 
    borderRadius: 8, 
    justifyContent: 'center', 
    alignItems: 'center', 
    marginTop: 16,
    elevation: 2
  },
  disabledBtn: { backgroundColor: '#A5D6A7' },
  searchBtnText: { color: '#FFF', fontWeight: 'bold', fontSize: 16 },
  sortSection: { 
    flexDirection: 'row', 
    paddingHorizontal: 20, 
    paddingVertical: 12, 
    backgroundColor: '#FFF' 
  },
  sortBtn: { 
    paddingHorizontal: 16, 
    paddingVertical: 8, 
    borderRadius: 20, 
    borderWidth: 1, 
    borderColor: '#EEE', 
    marginRight: 10 
  },
  activeSortBtn: { backgroundColor: '#E8F5E9', borderColor: '#2E7D32' },
  sortBtnText: { fontSize: 12, color: '#666' },
  activeSortText: { color: '#2E7D32', fontWeight: 'bold' },
  listContent: { padding: 20, paddingBottom: 40 },
  skeletonCard: { backgroundColor: '#EEE', height: 72, borderRadius: 12, marginBottom: 12, padding: 16, justifyContent: 'center' },
  skeletonRow: { height: 12, backgroundColor: '#DDD', borderRadius: 4 },
});

export default MarketPricesScreen;
