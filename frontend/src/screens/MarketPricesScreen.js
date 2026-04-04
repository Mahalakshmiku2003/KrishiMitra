import React, { useState, useEffect } from 'react';
import { 
  View, 
  Text, 
  StyleSheet, 
  TextInput, 
  TouchableOpacity, 
  FlatList, 
  Animated,
  SafeAreaView,
  Platform,
  ScrollView
} from 'react-native';
import { MaterialIcons } from '@expo/vector-icons';
import Toast from 'react-native-toast-message';
import { getMarketPrices } from '../api/market';
import EmptyState from '../components/EmptyState';
import { theme } from '../theme';

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
      <View style={styles.skeletonHeader}>
        <View>
          <View style={[styles.skeletonBlock, { width: 120, height: 18 }]} />
          <View style={[styles.skeletonBlock, { width: 80, height: 12, marginTop: 4 }]} />
        </View>
        <View style={[styles.skeletonBlock, { width: 24, height: 24, borderRadius: 12 }]} />
      </View>
      <View style={styles.skeletonFooter}>
        <View style={[styles.skeletonBlock, { width: 100, height: 24 }]} />
        <View style={[styles.skeletonBlock, { width: 60, height: 10 }]} />
      </View>
    </Animated.View>
  );
};

const MarketPricesScreen = ({ navigation }) => {
  const [commodity, setCommodity] = useState('Tomato');
  const [stateFilter, setStateFilter] = useState('');
  const [results, setResults] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [sortBy, setSortBy] = useState('price');

  const POPULAR_STATES = ['All States', 'Maharashtra', 'Karnataka', 'Uttar Pradesh', 'Gujarat'];

  // 🚀 Auto-load data on mount
  useEffect(() => {
    handleSearch();
  }, []);

  const handleSearch = async () => {
    if (!commodity.trim()) {
      Toast.show({ type: 'error', text1: 'Required', text2: 'Please enter a commodity name' });
      return;
    }
    
    setLoading(true);
    setError(null);
    setResults([]);

    try {
      const searchState = stateFilter === 'All States' ? '' : stateFilter;
      const response = await getMarketPrices(commodity, searchState);
      if (response.data && response.data.status === 'success') {
        const sorted = sortResults(response.data.prices, sortBy);
        setResults(sorted);
        if (sorted.length > 0) {
          Toast.show({ type: 'success', text1: 'Prices updated', text2: `Found ${sorted.length} markets for ${commodity}` });
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

  const selectStateFilter = (st) => {
    setStateFilter(st);
    // Auto trigger search on filter tap (slight delay to let state update if we were relying on it in useEffect, but we can just pass it directly)
    const searchState = st === 'All States' ? '' : st;
    triggerSearchWithParams(commodity, searchState);
  };

  const triggerSearchWithParams = async (cmd, st) => {
    setLoading(true);
    setError(null);
    setResults([]);
    try {
      const response = await getMarketPrices(cmd, st);
      if (response.data && response.data.status === 'success') {
        const sorted = sortResults(response.data.prices, sortBy);
        setResults(sorted);
      } else {
        setResults([]);
      }
    } catch (err) {
      setError("Could not fetch prices. Check your connection.");
    } finally {
      setLoading(false);
    }
  };

  const renderPriceCard = ({ item }) => {
    return (
      <View style={styles.priceCard}>
        <View style={styles.cardHeaderRow}>
          <View>
            <Text style={styles.cardTitle}>{item.commodity} • {item.market}</Text>
            <Text style={styles.cardStateText}>{item.state}</Text>
          </View>
          <MaterialIcons name="trending-up" size={24} color={theme.colors.primaryContainer} />
        </View>
        <View style={styles.cardFooterRow}>
          <View style={styles.priceContainer}>
            <Text style={styles.priceText}>
              ₹ {item.modal_price.toLocaleString('en-IN')}
            </Text>
            <Text style={styles.priceUnit}>/quintal</Text>
          </View>
          <Text style={styles.dateText}>{item.date}</Text>
        </View>
      </View>
    );
  };

  return (
    <SafeAreaView style={styles.safeArea}>
      <View style={styles.header}>
        <View style={styles.headerLeft}>
          <TouchableOpacity 
            style={styles.iconBtn} 
            onPress={() => navigation.goBack()}
            activeOpacity={0.7}
          >
            <MaterialIcons name="arrow-back" size={24} color={theme.colors.primary} />
          </TouchableOpacity>
          <Text style={styles.headerTitle}>Mandi Prices</Text>
        </View>
        <TouchableOpacity style={styles.iconBtn} activeOpacity={0.7}>
          <MaterialIcons name="search" size={24} color={theme.colors.primary} />
        </TouchableOpacity>
      </View>

      <View style={styles.container}>
        {/* Search Bar */}
        <View style={styles.searchSection}>
          <View style={styles.searchInputContainer}>
            <MaterialIcons name="search" size={20} color={theme.colors.onSurfaceVariant} style={{opacity: 0.6}} />
            <TextInput 
              style={styles.searchInput}
              placeholder="Search commodity e.g. Tomato"
              placeholderTextColor={theme.colors.outline}
              value={commodity}
              onChangeText={setCommodity}
              onSubmitEditing={handleSearch}
              returnKeyType="search"
            />
          </View>
        </View>

        {/* State Filters */}
        <View style={styles.filtersSection}>
          <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.filtersScrollContent}>
            {POPULAR_STATES.map((st, idx) => {
              const isActive = stateFilter === st || (st === 'All States' && !stateFilter);
              return (
                <TouchableOpacity 
                  key={idx}
                  style={[styles.filterChip, isActive && styles.filterChipActive]}
                  onPress={() => selectStateFilter(st)}
                  activeOpacity={0.8}
                >
                  <Text style={[styles.filterChipText, isActive && styles.filterChipTextActive]}>{st}</Text>
                </TouchableOpacity>
              )
            })}
          </ScrollView>
        </View>

        {/* Sorting and Metadata */}
        <View style={styles.metadataSection}>
          <View style={styles.sortToggleContainer}>
            <TouchableOpacity 
              style={[styles.sortSegment, sortBy === 'price' && styles.sortSegmentActive]}
              onPress={() => handleSortChange('price')}
              activeOpacity={0.8}
            >
              <Text style={[styles.sortSegmentText, sortBy === 'price' && styles.sortSegmentTextActive]}>Highest Price</Text>
            </TouchableOpacity>
            <TouchableOpacity 
              style={[styles.sortSegment, sortBy === 'date' && styles.sortSegmentActive]}
              onPress={() => handleSortChange('date')}
              activeOpacity={0.8}
            >
              <Text style={[styles.sortSegmentText, sortBy === 'date' && styles.sortSegmentTextActive]}>Most Recent</Text>
            </TouchableOpacity>
          </View>
          
          {(!loading && results.length > 0) && (
            <Text style={styles.resultCountText}>SHOWING {results.length} RESULTS FOR {commodity.toUpperCase()}</Text>
          )}
        </View>

        {/* List */}
        <FlatList
          data={loading ? [1, 2, 3, 4] : results}
          keyExtractor={(item, index) => index.toString()}
          renderItem={loading ? () => <SkeletonCard /> : renderPriceCard}
          contentContainerStyle={styles.listContent}
          showsVerticalScrollIndicator={false}
          ListEmptyComponent={() => !loading && (
            <EmptyState 
              icon="search-off" 
              title={error ? "Error Fetching Data" : "No prices found"} 
              subtitle={error ? error : "Try a different crop name or broaden your search."} 
            />
          )}
        />
      </View>
    </SafeAreaView>
  );
};

const styles = StyleSheet.create({
  safeArea: {
    flex: 1,
    backgroundColor: theme.colors.surface,
    paddingTop: Platform.OS === 'android' ? 40 : 0,
  },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 16,
    paddingVertical: 12,
    backgroundColor: theme.colors.surfaceContainerLow,
    borderBottomWidth: 1,
    borderBottomColor: 'rgba(226, 226, 226, 0.3)',
    zIndex: 10,
  },
  headerLeft: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  iconBtn: {
    padding: 8,
  },
  headerTitle: {
    fontSize: 20,
    fontWeight: '700',
    color: theme.colors.primary,
    letterSpacing: -0.5,
  },
  container: {
    flex: 1,
    paddingHorizontal: 24,
  },
  searchSection: {
    marginTop: 24,
  },
  searchInputContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: theme.colors.surfaceContainerLowest,
    height: 56,
    borderRadius: 999,
    paddingHorizontal: 16,
    gap: 12,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.05,
    shadowRadius: 8,
    elevation: 2,
  },
  searchInput: {
    flex: 1,
    fontSize: 16,
    color: theme.colors.onSurface,
    fontWeight: '500',
  },
  filtersSection: {
    marginTop: 24,
    marginHorizontal: -24, // Break out of container padding for full bleed scroll
  },
  filtersScrollContent: {
    paddingHorizontal: 24,
    gap: 8,
  },
  filterChip: {
    paddingHorizontal: 20,
    paddingVertical: 10,
    borderRadius: 999,
    backgroundColor: theme.colors.surfaceContainerLow,
    borderWidth: 1,
    borderColor: 'rgba(191, 202, 186, 0.3)',
  },
  filterChipActive: {
    backgroundColor: theme.colors.primary,
    borderColor: theme.colors.primary,
    shadowColor: theme.colors.primary,
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.2,
    shadowRadius: 4,
    elevation: 3,
  },
  filterChipText: {
    fontSize: 14,
    fontWeight: '600',
    color: theme.colors.onSurfaceVariant,
  },
  filterChipTextActive: {
    color: theme.colors.onPrimary,
  },
  metadataSection: {
    marginTop: 32,
    gap: 16,
  },
  sortToggleContainer: {
    flexDirection: 'row',
    backgroundColor: theme.colors.surfaceContainer,
    borderRadius: 999,
    padding: 4,
    alignSelf: 'flex-start',
    gap: 4,
  },
  sortSegment: {
    paddingHorizontal: 16,
    paddingVertical: 6,
    borderRadius: 999,
  },
  sortSegmentActive: {
    backgroundColor: theme.colors.primary,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.1,
    shadowRadius: 2,
    elevation: 1,
  },
  sortSegmentText: {
    fontSize: 12,
    fontWeight: '600',
    color: theme.colors.onSurfaceVariant,
  },
  sortSegmentTextActive: {
    color: theme.colors.onPrimary,
  },
  resultCountText: {
    fontSize: 12,
    fontWeight: '600',
    color: theme.colors.outline,
    letterSpacing: 1,
    ...theme.typography.label,
  },
  listContent: {
    paddingTop: 16,
    paddingBottom: 40,
    gap: 16,
  },
  priceCard: {
    backgroundColor: theme.colors.surfaceContainerLowest,
    borderRadius: 16,
    padding: 20,
    borderLeftWidth: 4,
    borderLeftColor: theme.colors.primary,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.04,
    shadowRadius: 12,
    elevation: 2,
  },
  cardHeaderRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
  },
  cardTitle: {
    fontSize: 18,
    fontWeight: '800',
    color: theme.colors.onSurface,
  },
  cardStateText: {
    fontSize: 12,
    fontWeight: '600',
    color: theme.colors.onSurfaceVariant,
    opacity: 0.7,
    marginTop: 2,
  },
  cardFooterRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'flex-end',
    marginTop: 16,
  },
  priceContainer: {
    flexDirection: 'row',
    alignItems: 'baseline',
  },
  priceText: {
    fontSize: 24,
    fontWeight: '900',
    color: theme.colors.primary,
    letterSpacing: -0.5,
  },
  priceUnit: {
    fontSize: 12,
    color: theme.colors.onSurfaceVariant,
    opacity: 0.6,
    marginLeft: 4,
  },
  dateText: {
    fontSize: 10,
    fontWeight: '700',
    color: theme.colors.outline,
    textTransform: 'uppercase',
    letterSpacing: 1,
    ...theme.typography.label,
  },
  skeletonCard: {
    backgroundColor: theme.colors.surfaceContainerLowest,
    borderRadius: 16,
    padding: 20,
    borderLeftWidth: 4,
    borderLeftColor: theme.colors.surfaceContainer,
  },
  skeletonHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
  },
  skeletonFooter: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'flex-end',
    marginTop: 16,
  },
  skeletonBlock: {
    backgroundColor: theme.colors.surfaceContainerHigh,
    borderRadius: 4,
  }
});

export default MarketPricesScreen;
