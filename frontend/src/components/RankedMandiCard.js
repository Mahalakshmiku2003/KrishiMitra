import React from 'react';
import { View, Text, StyleSheet } from 'react-native';

const RankedMandiCard = ({ rank, mandi, district, price, transportCost, netPrice }) => {
  const getBadgeColor = () => {
    if (rank === 1) return '#FFD700'; // Gold
    if (rank === 2) return '#C0C0C0'; // Silver
    if (rank === 3) return '#CD7F32'; // Bronze
    return '#E0E0E0'; // Grey
  };

  return (
    <View style={styles.card}>
      <View style={styles.row}>
        <View style={[styles.badge, { backgroundColor: getBadgeColor() }]}>
          <Text style={styles.badgeText}>#{rank}</Text>
        </View>
        <View style={styles.info}>
          <Text style={styles.mandiName}>{mandi}</Text>
          <Text style={styles.district}>{district}</Text>
        </View>
      </View>

      <View style={styles.priceRow}>
        <View>
          <Text style={styles.label}>Mandi Price</Text>
          <Text style={styles.value}>₹ {price}</Text>
        </View>
        <View>
          <Text style={styles.label}>Transport</Text>
          <Text style={styles.value}>₹ {transportCost}</Text>
        </View>
        <View style={styles.netContainer}>
          <Text style={styles.netLabel}>Net Price</Text>
          <Text style={styles.netValue}>₹ {netPrice}</Text>
        </View>
      </View>
    </View>
  );
};

const styles = StyleSheet.create({
  card: {
    backgroundColor: '#FFFFFF',
    borderRadius: 12,
    padding: 16,
    marginBottom: 16,
    elevation: 3,
    shadowColor: '#000',
    shadowOpacity: 0.1,
    shadowRadius: 4,
  },
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: 16,
  },
  badge: {
    width: 36,
    height: 36,
    borderRadius: 18,
    justifyContent: 'center',
    alignItems: 'center',
    marginRight: 12,
  },
  badgeText: {
    fontWeight: 'bold',
    fontSize: 14,
    color: '#FFF',
  },
  info: {
    flex: 1,
  },
  mandiName: {
    fontSize: 16,
    fontWeight: 'bold',
    color: '#333',
  },
  district: {
    fontSize: 13,
    color: '#9E9E9E',
  },
  priceRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    borderTopWidth: 1,
    borderTopColor: '#F5F5F5',
    paddingTop: 12,
  },
  label: {
    fontSize: 11,
    color: '#9E9E9E',
    marginBottom: 2,
  },
  value: {
    fontSize: 14,
    color: '#666',
  },
  netContainer: {
    backgroundColor: '#FFF8E1',
    paddingHorizontal: 12,
    paddingVertical: 8,
    borderRadius: 8,
    alignItems: 'center',
  },
  netLabel: {
    fontSize: 10,
    color: '#F9A825',
    fontWeight: 'bold',
    marginBottom: 2,
  },
  netValue: {
    fontSize: 15,
    fontWeight: 'bold',
    color: '#F9A825',
  },
});

export default RankedMandiCard;
