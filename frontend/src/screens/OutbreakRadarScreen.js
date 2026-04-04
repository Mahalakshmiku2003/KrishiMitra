import React, { useState, useEffect, useRef } from 'react';
import { 
  View, 
  Text, 
  ScrollView, 
  FlatList, 
  TouchableOpacity, 
  StyleSheet, 
  Dimensions, 
  SafeAreaView, 
  Animated 
} from 'react-native';
import Svg, { Path, Circle, G } from 'react-native-svg';
import { Ionicons, MaterialIcons } from '@expo/vector-icons';

const { width } = Dimensions.get('window');

// --- Mock Data ---
const OUTBREAK_DATA = [
  { id: 1, disease: "Early Blight", crop: "Tomato", 
    region: "Nashik, Maharashtra", severity: "High", 
    farms_affected: 142, reported_date: "2026-04-01",
    lat: 20.0, indicator: "🔴", x: 80, y: 195 },
  { id: 2, disease: "Powdery Mildew", crop: "Wheat", 
    region: "Ludhiana, Punjab", severity: "Medium",
    farms_affected: 87, reported_date: "2026-04-01",
    lat: 30.9, indicator: "🟡", x: 105, y: 75 },
  { id: 3, disease: "Leaf Rust", crop: "Wheat", 
    region: "Karnal, Haryana", severity: "High",
    farms_affected: 203, reported_date: "2026-03-31",
    lat: 29.7, indicator: "🔴", x: 115, y: 90 },
  { id: 4, disease: "Brown Spot", crop: "Rice", 
    region: "Warangal, Telangana", severity: "Low",
    farms_affected: 34, reported_date: "2026-03-30",
    lat: 18.0, indicator: "🟢", x: 145, y: 225 },
  { id: 5, disease: "Bacterial Blight", crop: "Rice", 
    region: "Thanjavur, Tamil Nadu", severity: "Medium",
    farms_affected: 91, reported_date: "2026-03-30",
    lat: 10.7, indicator: "🟡", x: 155, y: 310 },
  { id: 6, disease: "Downy Mildew", crop: "Grapes", 
    region: "Pune, Maharashtra", severity: "High",
    farms_affected: 178, reported_date: "2026-04-01",
    lat: 18.5, indicator: "🔴", x: 85, y: 215 },
  { id: 7, disease: "Fusarium Wilt", crop: "Cotton", 
    region: "Nagpur, Maharashtra", severity: "Medium",
    farms_affected: 56, reported_date: "2026-03-29",
    lat: 21.1, indicator: "🟡", x: 135, y: 185 },
  { id: 8, disease: "Stem Borer", crop: "Sugarcane", 
    region: "Kolhapur, Maharashtra", severity: "Low",
    farms_affected: 29, reported_date: "2026-03-28",
    lat: 16.7, indicator: "🟢", x: 82, y: 235 },
];

const CROP_FILTERS = ["All", "Tomato", "Wheat", "Rice", "Grapes", "Cotton", "Sugarcane"];

// Colors
const SEVERITY_COLORS = {
  High: '#C62828',
  Medium: '#F9A825',
  Low: '#2E7D32',
};

const SEVERITY_BG = {
  High: '#FFEBEE',
  Medium: '#FFF8E1',
  Low: '#E8F5E9',
};

const PulsingMarker = ({ x, y, farms, severity }) => {
  const pulseAnim = useRef(new Animated.Value(1)).current;

  useEffect(() => {
    if (severity === 'High') {
      Animated.loop(
        Animated.sequence([
          Animated.timing(pulseAnim, {
            toValue: 1.3,
            duration: 1000,
            useNativeDriver: true,
          }),
          Animated.timing(pulseAnim, {
            toValue: 1,
            duration: 1000,
            useNativeDriver: true,
          }),
        ])
      ).start();
    }
  }, [severity]);

  const radius = farms > 150 ? 14 : farms > 80 ? 11 : 8;
  const color = SEVERITY_COLORS[severity];

  return (
    <G>
      {severity === 'High' && (
        <Animated.View
          style={{
            position: 'absolute',
            left: x - radius * 1.5,
            top: y - radius * 1.5,
            width: radius * 3,
            height: radius * 3,
            borderRadius: radius * 1.5,
            backgroundColor: color,
            opacity: pulseAnim.interpolate({
              inputRange: [1, 1.3],
              outputRange: [0.6, 0],
            }),
            transform: [{ scale: pulseAnim }],
          }}
        />
      )}
      <Circle
        cx={x}
        cy={y}
        r={radius}
        fill={color}
        stroke="white"
        strokeWidth="2"
      />
    </G>
  );
};

const OutbreakRadarScreen = () => {
  const [selectedCrop, setSelectedCrop] = useState("All");
  const fadeAnim = useRef(new Animated.Value(0)).current;
  const slideAnim = useRef(new Animated.Value(30)).current;

  const filteredData = selectedCrop === "All" 
    ? OUTBREAK_DATA 
    : OUTBREAK_DATA.filter(item => item.crop === selectedCrop);

  // Staggered fade-in
  useEffect(() => {
    Animated.parallel([
      Animated.timing(fadeAnim, {
        toValue: 1,
        duration: 800,
        useNativeDriver: true,
      }),
      Animated.timing(slideAnim, {
        toValue: 0,
        duration: 800,
        useNativeDriver: true,
      }),
    ]).start();
  }, []);

  const stats = {
    high: OUTBREAK_DATA.filter(i => i.severity === 'High').length,
    farms: OUTBREAK_DATA.reduce((sum, i) => sum + i.farms_affected, 0),
    diseases: new Set(OUTBREAK_DATA.map(i => i.disease)).size,
  };

  const renderHeader = () => (
    <View style={styles.header}>
      <View>
        <Text style={styles.title}>🗺️ Outbreak Radar</Text>
        <Text style={styles.subtitle}>Live disease alerts across India</Text>
      </View>
      <View style={styles.updatedPill}>
        <Text style={styles.updatedText}>Last updated: Apr 1, 2026</Text>
      </View>
    </View>
  );

  const renderStats = () => (
    <View style={styles.statsRow}>
      <View style={[styles.statCard, { backgroundColor: '#FFEBEE' }]}>
        <Text style={[styles.statNumber, { color: '#C62828' }]}>{stats.high}</Text>
        <Text style={[styles.statLabel, { color: '#C62828' }]}>Active Outbreaks</Text>
      </View>
      <View style={[styles.statCard, { backgroundColor: '#FFF8E1' }]}>
        <Text style={[styles.statNumber, { color: '#F9A825' }]}>{stats.farms}</Text>
        <Text style={[styles.statLabel, { color: '#F9A825' }]}>Farms Affected</Text>
      </View>
      <View style={[styles.statCard, { backgroundColor: '#E3F2FD' }]}>
        <Text style={[styles.statNumber, { color: '#1976D2' }]}>{stats.diseases}</Text>
        <Text style={[styles.statLabel, { color: '#1976D2' }]}>Diseases Tracked</Text>
      </View>
    </View>
  );

  const renderMap = () => (
    <View style={styles.mapCard}>
      <View style={styles.svgContainer}>
        <Svg width="100%" height="340" viewBox="0 0 300 340">
          {/* Detailed India Map Outline */}
          <Path
            d="M140 20 L150 10 L160 15 L165 30 L180 40 L195 45 L200 60 L220 70 L230 100 
               L225 130 L235 150 L270 145 L285 135 L295 150 L280 170 L260 165 L245 180 
               L250 205 L230 230 L210 240 L190 260 L175 290 L165 320 L155 335 L145 325 
               L135 300 L120 270 L110 240 L90 220 L75 230 L50 215 L35 200 L25 160 L45 145 
               L60 155 L75 135 L85 110 L100 75 L115 50 L125 35 L140 20 Z"
            fill="#E8F5E9"
            stroke="#1B5E20"
            strokeWidth="2"
            strokeLinejoin="round"
          />
          {/* Subtle State Boundaries for realism */}
          <Path
            d="M115 130 L145 125 L180 140 M190 180 L145 190 L80 195 M135 240 L175 245"
            fill="none"
            stroke="#1B5E20"
            strokeWidth="0.5"
            opacity="0.3"
          />
          {OUTBREAK_DATA.map(item => (
            <PulsingMarker 
              key={item.id} 
              x={item.x} 
              y={item.y} 
              farms={item.farms_affected} 
              severity={item.severity} 
            />
          ))}
        </Svg>
      </View>
      <View style={styles.legend}>
        <Text style={styles.legendItem}>🔴 High</Text>
        <Text style={styles.legendItem}>🟡 Medium</Text>
        <Text style={styles.legendItem}>🟢 Low</Text>
      </View>
    </View>
  );

  const renderFilters = () => (
    <ScrollView 
      horizontal 
      showsHorizontalScrollIndicator={false} 
      contentContainerStyle={styles.filterScroll}
    >
      {CROP_FILTERS.map(crop => (
        <TouchableOpacity
          key={crop}
          onPress={() => setSelectedCrop(crop)}
          style={[
            styles.filterChip,
            selectedCrop === crop ? styles.filterChipActive : styles.filterChipInactive
          ]}
        >
          <Text style={[
            styles.filterText,
            selectedCrop === crop ? styles.filterTextActive : styles.filterTextInactive
          ]}>
            {crop}
          </Text>
        </TouchableOpacity>
      ))}
    </ScrollView>
  );

  const renderItem = ({ item, index }) => (
    <Animated.View style={[
      styles.outbreakCard,
      {
        opacity: fadeAnim,
        transform: [{ translateY: slideAnim }],
        borderLeftColor: SEVERITY_COLORS[item.severity],
        borderLeftWidth: 4,
      }
    ]}>
      <View style={styles.cardTop}>
        <View style={styles.cardInfo}>
          <Text style={styles.diseaseTitle}>{item.indicator} {item.disease}</Text>
        </View>
        <View style={[styles.badge, { backgroundColor: SEVERITY_COLORS[item.severity] }]}>
          <Text style={styles.badgeText}>{item.severity}</Text>
        </View>
      </View>

      <View style={styles.cardMiddle}>
        <View style={styles.cropBadge}>
          <Text style={styles.cropBadgeText}>🌿 {item.crop}</Text>
        </View>
        <Text style={styles.regionText}>📍 {item.region}</Text>
      </View>

      <View style={styles.cardBottom}>
        <Text style={styles.farmStats}>🏚️ {item.farms_affected} farms affected</Text>
        <Text style={styles.dateText}>📅 {item.reported_date}</Text>
      </View>
    </Animated.View>
  );

  const renderEmpty = () => (
    <View style={styles.emptyContainer}>
      <Text style={styles.emptyEmoji}>🌿</Text>
      <Text style={styles.emptyTitle}>No outbreaks reported</Text>
      <Text style={styles.emptySubtitle}>This crop region looks healthy</Text>
    </View>
  );

  return (
    <SafeAreaView style={styles.container}>
      <FlatList
        data={filteredData}
        renderItem={renderItem}
        keyExtractor={item => item.id.toString()}
        ListHeaderComponent={() => (
          <View>
            {renderHeader()}
            {renderStats()}
            {renderMap()}
            {renderFilters()}
            <Text style={styles.listHeader}>
              Reported Outbreaks <Text style={styles.listCount}>({filteredData.length})</Text>
            </Text>
          </View>
        )}
        ListEmptyComponent={renderEmpty}
        contentContainerStyle={styles.scrollContent}
        showsVerticalScrollIndicator={false}
      />
    </SafeAreaView>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#F5F5F5',
  },
  scrollContent: {
    paddingBottom: 20,
  },
  header: {
    padding: 20,
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
  },
  title: {
    fontSize: 24,
    fontWeight: 'bold',
    color: '#1B5E20',
  },
  subtitle: {
    fontSize: 13,
    color: '#666',
    marginTop: 4,
  },
  updatedPill: {
    backgroundColor: '#E0E0E0',
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderRadius: 20,
  },
  updatedText: {
    fontSize: 10,
    color: '#666',
  },
  statsRow: {
    flexDirection: 'row',
    paddingHorizontal: 15,
    justifyContent: 'space-between',
    marginBottom: 20,
  },
  statCard: {
    width: (width - 50) / 3,
    padding: 12,
    borderRadius: 12,
    alignItems: 'center',
    backgroundColor: 'white',
    elevation: 2,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.1,
    shadowRadius: 2,
  },
  statNumber: {
    fontSize: 20,
    fontWeight: 'bold',
  },
  statLabel: {
    fontSize: 10,
    marginTop: 4,
    textAlign: 'center',
    fontWeight: '600',
  },
  mapCard: {
    backgroundColor: 'white',
    marginHorizontal: 20,
    borderRadius: 12,
    padding: 15,
    elevation: 3,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.1,
    shadowRadius: 4,
    marginBottom: 20,
  },
  svgContainer: {
    alignItems: 'center',
    justifyContent: 'center',
  },
  legend: {
    flexDirection: 'row',
    justifyContent: 'center',
    marginTop: 15,
    gap: 15,
  },
  legendItem: {
    fontSize: 12,
    color: '#666',
  },
  filterScroll: {
    paddingHorizontal: 20,
    marginBottom: 20,
  },
  filterChip: {
    paddingHorizontal: 16,
    paddingVertical: 8,
    borderRadius: 20,
    marginRight: 10,
    borderWidth: 1,
  },
  filterChipActive: {
    backgroundColor: '#2E7D32',
    borderColor: '#2E7D32',
  },
  filterChipInactive: {
    backgroundColor: 'white',
    borderColor: '#2E7D32',
  },
  filterText: {
    fontSize: 14,
    fontWeight: '600',
  },
  filterTextActive: {
    color: 'white',
  },
  filterTextInactive: {
    color: '#2E7D32',
  },
  listHeader: {
    fontSize: 18,
    fontWeight: 'bold',
    paddingHorizontal: 20,
    marginBottom: 15,
    color: '#333',
  },
  listCount: {
    fontSize: 14,
    fontWeight: 'normal',
    color: '#666',
  },
  outbreakCard: {
    backgroundColor: 'white',
    marginHorizontal: 20,
    borderRadius: 12,
    padding: 14,
    marginBottom: 10,
    elevation: 2,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.1,
    shadowRadius: 2,
  },
  cardTop: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 10,
  },
  cardInfo: {
    flex: 1,
  },
  diseaseTitle: {
    fontSize: 16,
    fontWeight: 'bold',
    color: '#333',
  },
  badge: {
    paddingHorizontal: 8,
    paddingVertical: 4,
    borderRadius: 8,
  },
  badgeText: {
    color: 'white',
    fontSize: 11,
    fontWeight: 'bold',
  },
  cardMiddle: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: 10,
    gap: 10,
  },
  cropBadge: {
    backgroundColor: '#E8F5E9',
    paddingHorizontal: 8,
    paddingVertical: 2,
    borderRadius: 4,
  },
  cropBadgeText: {
    fontSize: 12,
    color: '#2E7D32',
    fontWeight: '500',
  },
  regionText: {
    fontSize: 13,
    color: '#666',
  },
  cardBottom: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    paddingTop: 8,
    borderTopWidth: 0.5,
    borderTopColor: '#EEE',
  },
  farmStats: {
    fontSize: 11,
    color: '#777',
  },
  dateText: {
    fontSize: 11,
    color: '#777',
  },
  emptyContainer: {
    alignItems: 'center',
    marginTop: 50,
  },
  emptyEmoji: {
    fontSize: 50,
    marginBottom: 10,
  },
  emptyTitle: {
    fontSize: 18,
    fontWeight: 'bold',
    color: '#333',
  },
  emptySubtitle: {
    fontSize: 14,
    color: '#666',
    marginTop: 5,
  },
});

export default OutbreakRadarScreen;
