import os
import sys

# Adjust path to find sibling imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

def compile_rj_template(segment_type: str, context_details: dict) -> str:
    """
    Compiles weather updates, mandi rates, and dedications into structured Bundeli RJ script drafts.
    """
    mandi_rates = context_details.get("mandi_rates", [])
    sarafa_rates = context_details.get("sarafa_rates", [])
    dedications = context_details.get("dedications", [])
    birthday_wishes = context_details.get("birthday_wishes", [])
    weather = context_details.get(
        "weather",
        "Mausam ka real update abhi configured source se verified nahi hai; broadcast se pehle manual/API check required hai."
    )
    
    script_parts = []
    
    if segment_type == "mandi_report":
        script_parts.append("Namaskar bhaiya aur behno! Orai Radio 90.8 FM par aap sabhi ka swagat hai, main hoon aapki RJ Neena.")
        script_parts.append("Chaliye sunte hain Bundelkhand ke Orai Mandi aur Sarafa Bazaar ke taaza bhav.")
        script_parts.append(f"Aaj ka mausam: {weather}")
        
        if mandi_rates:
            script_parts.append("Mandi ke taza bhav is prakar hain:")
            for item in mandi_rates:
                trend_word = "badhakar" if item.get("trend") == "up" else "ghatakar"
                script_parts.append(f"- {item.get('item_name')}: Roopoye {item.get('price')} {item.get('unit')} ho gaya hai, jo ki pichle bhav se {item.get('price_change')} {trend_word} hai.")
        
        if sarafa_rates:
            script_parts.append("Sarafa Bazaar me sone chandi ka bhav:")
            for item in sarafa_rates:
                trend_word = "tezi" if item.get("trend") == "up" else "mandi"
                script_parts.append(f"- {item.get('item_name')}: Roopoye {item.get('price')} {item.get('unit')} par hai, isme {item.get('price_change')} ki {trend_word} dekhi gayi.")
                
        script_parts.append("Orai Mandi ke bhav ke sath jude rahiye aur sunte rahiye Orai Radio! Hum jald hi lautenge ek aur taza report ke sath.")
        
    elif segment_type == "farmaish_capsule":
        script_parts.append("Ram Ram bhaiya aur behno! Swagat hai aap sabhi ka Orai Radio ke Farmaish Capsule show me, main aapki RJ Neena.")
        
        if not dedications and not birthday_wishes:
            script_parts.append("Lekin shrotaon, aaj hamari farmaish queue bilkul khali hai. Orai Radio database me abhi koi bhi approved song request ya birthday wish queue me nahi hai. Aap sabhi log apne gaane aur sandesh hamare WhatsApp number par bhej sakte hain, taaki agle show me hum unhe shamil kar sakein!")
        else:
            script_parts.append("Aaj hamare shrotaon ne apne dosto aur pariwar ke liye dher saare geet aur sandesh bheje hain.")
            
            if dedications:
                script_parts.append("Chaliye pehli farmaish ki taraf chalte hain:")
                for d in dedications:
                    script_parts.append(f"- Hamare shrota {d.get('listener_name')} jo {d.get('region')} se hain, unhone '{d.get('song_title')}' gaane ki farmaish ki hai apne priya {d.get('dedicated_to')} ke liye. Unka sandesh hai: '{d.get('message') or 'Koi sandesh nahi'}'")
            
            if birthday_wishes:
                script_parts.append("Aur ab, janmadin ke khas shubhkamnaayein!")
                for w in birthday_wishes:
                    script_parts.append(f"- {w.get('listener_name')} jo {w.get('region')} se hain, unhone {w.get('wish_for')} ko janmadin ki badhai bheji hai! Unka pyara sandesh hai: '{w.get('message') or 'Janmadin Mubarak!'}'")
                    
            script_parts.append("Ye farmaish draft queue me note ho gayi hai. Broadcast ya gaana play karne se pehle owner approval aur schedule confirmation required hai.")
        
    else:
        # Default fallback template
        script_parts.append("Namaskar bhaiya aur behno! Orai Radio par aapka swagat hai, main hoon RJ Neena.")
        script_parts.append(f"Chaliye aaj ki regional khabre aur mausam par dhyan dete hain. {weather}")
        script_parts.append("Hamare sath bane rahiye, aur local gaane sunte rahiye.")
        
    full_script = "\n\n".join(script_parts)
    return f"[SCRIPT_OUTPUT]\n{full_script}\n[/SCRIPT_OUTPUT]"
