import React from 'react';
import { View, Text, StyleSheet } from 'react-native';

const PriceCard = ({ commodity, market, state, price, date }) => {
  return (
    <View style={styles.card}>
      <View style={styles.header}>
        <Text style={styles.title}>{commodity} • {market}</Text>
        <Text style={styles.state}>{state}</Text>
      </View>
      <View style={styles.footer}>
        <Text style={styles.price}>₹ {price}/quintal</Text>
        <Text style={styles.date}>{date}</Text>
      </View>
    </View>
  );
};

const styles = StyleSheet.create({
  card: {
    backgroundColor: '#FFFFFF',
    borderRadius: 12,
    padding: 16,
    marginBottom: 12,
    elevation: 3,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.1,
    shadowRadius: 3,
  },
  header: {
    marginBottom: 12,
  },
  title: {
    fontSize: 16,
    fontWeight: 'bold',
    color: '#333',
  },
  state: {
    fontSize: 12,
    color: '#9E9E9E',
    marginTop: 2,
  },
  footer: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'baseline',
  },
  price: {
    fontSize: 18,
    fontWeight: 'bold',
    color: '#2E7D32',
  },
  date: {
    fontSize: 11,
    color: '#9E9E9E',
  },
});

export default PriceCard;
