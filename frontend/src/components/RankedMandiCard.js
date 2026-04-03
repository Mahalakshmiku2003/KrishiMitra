import React from 'react';
import { View, Text, StyleSheet } from 'react-native';
import { theme } from '../theme';

const RankedMandiCard = ({ rank, mandi, district, price, transportCost, netPrice }) => {
  const getBadgeColor = () => {
    if (rank === 1) return '#FFD700'; // Gold
    if (rank === 2) return '#9E9E9E'; // Silver
    if (rank === 3) return '#CD7F32'; // Bronze
    return theme.colors.outline; 
  };

  const badgeColor = getBadgeColor();

  return (
    <View style={[styles.card, { borderLeftColor: badgeColor }]}>
      <View style={styles.topSection}>
        <View style={styles.mandiInfo}>
          <View style={[styles.rankBadge, { backgroundColor: badgeColor }]}>
            <Text style={styles.rankText}>#{rank}</Text>
          </View>
          <View>
            <Text style={styles.mandiName}>{mandi}</Text>
            <Text style={styles.districtName}>{district}</Text>
          </View>
        </View>
        
        <View style={styles.netPriceBadge}>
          <Text style={styles.netPriceLabel}>ESTIMATED NET</Text>
          <Text style={styles.netPriceValue}>
            ₹{Number(netPrice).toLocaleString('en-IN')}
          </Text>
        </View>
      </View>

      <View style={styles.bottomSection}>
        <View style={styles.detailColumn}>
          <Text style={styles.detailLabel}>MANDI PRICE</Text>
          <Text style={styles.detailValue}>
            ₹{Number(price).toLocaleString('en-IN')} <Text style={styles.detailUnit}>/ quintal</Text>
          </Text>
        </View>
        <View style={[styles.detailColumn, { alignItems: 'flex-end' }]}>
          <Text style={styles.detailLabel}>TRANSPORT</Text>
          <Text style={[styles.detailValue, { color: theme.colors.error }]}>
            ₹{Number(transportCost).toLocaleString('en-IN')}
          </Text>
        </View>
      </View>
    </View>
  );
};

const styles = StyleSheet.create({
  card: {
    backgroundColor: theme.colors.surfaceContainerLowest,
    borderRadius: 12,
    padding: 20,
    marginBottom: 16,
    borderLeftWidth: 4,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.03,
    shadowRadius: 16,
    elevation: 2,
  },
  topSection: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
    marginBottom: 20,
  },
  mandiInfo: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
  },
  rankBadge: {
    width: 40,
    height: 40,
    borderRadius: 20,
    alignItems: 'center',
    justifyContent: 'center',
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.1,
    shadowRadius: 4,
    elevation: 1,
  },
  rankText: {
    color: '#FFF',
    fontSize: 16,
    fontWeight: '800',
  },
  mandiName: {
    fontSize: 18,
    fontWeight: '800',
    color: theme.colors.onSurface,
    lineHeight: 22,
  },
  districtName: {
    fontSize: 14,
    fontWeight: '500',
    color: theme.colors.onSurfaceVariant,
  },
  netPriceBadge: {
    backgroundColor: '#FFF8E1',
    paddingHorizontal: 12,
    paddingVertical: 8,
    borderRadius: 12,
    alignItems: 'flex-end',
  },
  netPriceLabel: {
    fontSize: 9,
    fontWeight: '800',
    color: theme.colors.tertiaryContainer,
    textTransform: 'uppercase',
    letterSpacing: 0.5,
    marginBottom: 2,
  },
  netPriceValue: {
    fontSize: 18,
    fontWeight: '800',
    color: theme.colors.primary,
    lineHeight: 22,
  },
  bottomSection: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    paddingTop: 16,
    borderTopWidth: 1,
    borderTopColor: theme.colors.surfaceContainer,
  },
  detailColumn: {
    gap: 4,
  },
  detailLabel: {
    fontSize: 10,
    fontWeight: '700',
    color: theme.colors.onSurfaceVariant,
    textTransform: 'uppercase',
    letterSpacing: -0.5,
  },
  detailValue: {
    fontSize: 14,
    fontWeight: '700',
    color: theme.colors.onSurface,
  },
  detailUnit: {
    fontSize: 10,
    fontWeight: '400',
  },
});

export default RankedMandiCard;
