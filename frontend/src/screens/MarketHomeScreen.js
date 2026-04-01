import React from 'react';
import { 
  View, 
  Text, 
  StyleSheet, 
  TouchableOpacity, 
  ScrollView 
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';

const MarketHomeScreen = ({ navigation }) => {
  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      <Text style={styles.header}>Market Intelligence 💰</Text>

      <TouchableOpacity 
        style={styles.card} 
        onPress={() => navigation.navigate('MarketPrices')}
      >
        <View style={styles.cardIcon}>
          <Ionicons name="bar-chart" size={32} color="#2E7D32" />
        </View>
        <View style={styles.cardText}>
          <Text style={styles.cardTitle}>📊 Mandi Prices</Text>
          <Text style={styles.cardSubtitle}>Latest prices across India</Text>
        </View>
      </TouchableOpacity>

      <TouchableOpacity 
        style={styles.card} 
        onPress={() => navigation.navigate('NearbyMandis')}
      >
        <View style={styles.cardIcon}>
          <Ionicons name="location" size={32} color="#F9A825" />
        </View>
        <View style={styles.cardText}>
          <Text style={styles.cardTitle}>📍 Nearby Mandis</Text>
          <Text style={styles.cardSubtitle}>Best price near your location</Text>
        </View>
      </TouchableOpacity>

      <TouchableOpacity 
        style={styles.card} 
        onPress={() => navigation.navigate('PricePrediction')}
      >
        <View style={styles.cardIcon}>
          <Ionicons name="trending-up" size={32} color="#2E7D32" />
        </View>
        <View style={styles.cardText}>
          <Text style={styles.cardTitle}>📈 Price Forecast</Text>
          <Text style={styles.cardSubtitle}>7-day AI prediction trends</Text>
        </View>
      </TouchableOpacity>

      <View style={styles.footer}>
        <Ionicons name="information-circle-outline" size={16} color="#9E9E9E" />
        <Text style={styles.footerText}>Prices updated daily from data.gov.in</Text>
      </View>
    </ScrollView>
  );
};

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#F5F5F5' },
  content: { padding: 24, paddingTop: 60 },
  header: { fontSize: 24, fontWeight: 'bold', color: '#2E7D32', marginBottom: 30 },
  card: { 
    width: '100%', 
    height: 100, 
    backgroundColor: '#FFF', 
    borderRadius: 12, 
    flexDirection: 'row', 
    alignItems: 'center', 
    paddingHorizontal: 20, 
    marginBottom: 20,
    elevation: 3,
    shadowColor: '#000',
    shadowOpacity: 0.1,
    shadowRadius: 4
  },
  cardIcon: { 
    width: 50, 
    height: 50, 
    borderRadius: 25, 
    backgroundColor: '#F0F4F0', 
    justifyContent: 'center', 
    alignItems: 'center',
    marginRight: 15
  },
  cardText: { flex: 1 },
  cardTitle: { fontSize: 18, fontWeight: 'bold', color: '#333' },
  cardSubtitle: { fontSize: 14, color: '#9E9E9E', marginTop: 2 },
  footer: { 
    flexDirection: 'row', 
    justifyContent: 'center', 
    alignItems: 'center', 
    marginTop: 40 
  },
  footerText: { fontSize: 13, color: '#9E9E9E', marginLeft: 6 }
});

export default MarketHomeScreen;
